import copy
import importlib
import os
import json
import hydra
from tqdm import tqdm
from omegaconf import DictConfig, OmegaConf

# llm class
from gpt4 import GPT4Agent
from azure import AsyncAzureChatLLM

"""
from scai.chat_models.crfm import crfmChatLLM
from langchain.chat_models import ChatOpenAI
from langchain.chat_models.base import BaseChatModel
"""

# set up context
from scai.games.dictator_games.context import Context
from scai.games.dictator_games.prompts.task.task_prompt import DICTATOR_TASK_PROMPTS, DECIDER_TASK_PROMPTS   
from generate_config import get_num_interactions, generate_agents, generate_interactions, generate_random_params, generate_starting_message

# save and plot results
from utils import save_as_csv
from plots import plot_results, plot_all_averages, plot_questions
from generalize_utils import agent_pick_contract, create_prompt_string, set_args, set_args_2, reset_args_2, get_existing_data

# create context
def create_context(
    args: DictConfig, 
    assistant_llm, 
    user_llm, 
    meta_llm,
    oracle_llm,
    Context,
    DICTATOR_TASK_PROMPTS, 
    DECIDER_TASK_PROMPTS, 
    META_PROMPTS
) -> "Context":
    """
    Create context
    """
    return Context.create(
        _id=args.sim.sim_id,
        name=args.sim.sim_dir,
        task_prompt_dictator = DICTATOR_TASK_PROMPTS[args.env.task_prompt],
        task_prompt_decider = DECIDER_TASK_PROMPTS[args.env.task_prompt],
        meta_prompt=META_PROMPTS[args.env.meta_prompt],
        user_llm=user_llm,
        assistant_llm=assistant_llm,
        meta_llm=meta_llm,
        oracle_llm=oracle_llm,
        verbose=args.sim.verbose,
        test_run=args.sim.test_run,
        amounts_per_run=args.env.amounts_per_run,
        n_fixed_inter=args.env.n_fixed_inter,
        n_mixed_inter=args.env.n_mixed_inter,
        n_flex_inter=args.env.n_flex_inter,
        currencies=args.env.currencies,
        agents_dict=args.agents,
        interactions_dict=args.interactions,
        edge_case_instructions=args.env.edge_cases.selected_contract if args.env.edge_cases.selected_contract else "",
        include_reason=args.env.edge_cases.reason.include_reason,
        propose_decide_alignment=args.env.propose_decide_alignment,
        has_manners = (args.env.single_fixed_manners == "neutral"),
        ask_question=args.env.edge_cases.conditions.ask_question,
        ask_question_train=args.env.ask_question_train,
        bph_norm = args.sim.norm,
        bph_bp = args.sim.best_policy,
    )

# create llms to be used in context
def get_llms(args):
    args.model.azure_api.api_key = os.getenv("OPENAI_API_KEY") # set api key, ANA
    assistant_llm = GPT4Agent(llm = AsyncAzureChatLLM(**args.model.azure_api), **args.model.completion_config)
    user_llm = GPT4Agent(llm = AsyncAzureChatLLM(**args.model.azure_api), **args.model.completion_config)
    meta_llm = GPT4Agent(llm = AsyncAzureChatLLM(**args.model.azure_api), **args.model.completion_config)
    oracle_llm = GPT4Agent(llm = AsyncAzureChatLLM(**args.model.azure_api), **args.model.completion_config)
    return assistant_llm, user_llm, meta_llm, oracle_llm

def run(args):

    #create a copy of the config file and experiment description for reference
    config_directory=f'{hydra.utils.get_original_cwd()}/experiments/{args.sim.sim_dir}/config_history'
    os.makedirs(config_directory, exist_ok=True)
    with open(f'{config_directory}/config_original', "w") as f: f.write(OmegaConf.to_yaml(args))
    with open(f"{config_directory}/../description", "w") as f: f.write(args.sim.description)
    
    # llms
    is_crfm = 'openai' in args.sim.model_name # custom stanford models
    assistant_llm, user_llm, meta_llm, oracle_llm = get_llms(args)

    num_experiments = args.env.random.n_rand_iter if not args.env.manual_run else 1
    original_currencies = args.env.currencies
    total_scores, all_score_lsts = [], []

    all_currencies = set()
    all_contracts = []
    cur_amount_min, cur_amount_max = float('inf'), float('-inf')
    all_questions = []
    currencies_and_questions = {}

    for i in range(num_experiments):

        # create directory and placeholders for results
        
        if args.env.edge_cases.activate:
            args.sim.sim_id = f"ref_{args.env.currencycounter}_{i}"
        else:
            args.sim.sim_id = f"{args.env.currencies}_{i}"
        args.env.currencies = original_currencies
        DATA_DIR = f'{hydra.utils.get_original_cwd()}/experiments/{args.sim.sim_dir}/{args.sim.sim_id}'
        os.makedirs(DATA_DIR, exist_ok=True)
        system_message = args.sim.system_message
        system_messages = []
        scores = []
        questions = []
        # set run id, amonts, and the currency; and saving to config
        if not args.env.manual_run:
            generate_starting_message(args)
            generate_random_params(args)
            generate_agents(args)
            generate_interactions(args)

        with open(f"{DATA_DIR}/id_{args.sim.sim_id}_config", "w") as f: f.write(OmegaConf.to_yaml(args))
        with open(f'{config_directory}/id_{args.sim.sim_id}_config', "w") as f: f.write(OmegaConf.to_yaml(args))

        # run meta-prompt
        for run in tqdm(range(args.env.n_runs)):

            # get interaction numbers
            get_num_interactions(args, 0)
            get_num_interactions(args, run)
            n_fixed = 1 if args.env.n_fixed_inter else 0
            n_mixed = 1 if args.env.n_mixed_inter else 0
            n_flex = 1 if args.env.n_flex_inter else 0

            #import appropriate metaprompt
            game_number = int(f"{int(n_fixed)}{int(n_mixed)}{int(n_flex)}", 2)
            meta_module = importlib.import_module(f"scai.games.dictator_games.meta_prompts.dictator_{game_number}_meta_prompts")
            META_PROMPTS = meta_module.META_PROMPTS

            # initialize context
            context = create_context(args, assistant_llm, user_llm, meta_llm, oracle_llm, Context,     
                                    DICTATOR_TASK_PROMPTS, DECIDER_TASK_PROMPTS, META_PROMPTS)

            context.buffer.save_system_context(model_id='system', **{
                'response': system_message,
            })
            # Keep track of the system messages
            system_messages.append(system_message)

            # run context - this runs the simulation
            user_scores_dictator, user_scores_decider, assistant_scores_dictator, assistant_scores_decider, user_proposals, assistant_proposals, question, norm, best_policy = context.run(run)
            scores.append((user_scores_dictator, user_scores_decider, assistant_scores_dictator, assistant_scores_decider, user_proposals, assistant_proposals))
            args.sim.norm = norm
            args.sim.best_policy = best_policy

            # save results as csv
            save_as_csv(system_data=context.buffer._system_memory.messages,
                        chat_data=context.buffer._chat_memory.messages,
                        data_directory=DATA_DIR, 
                        sim_name=args.sim.sim_dir,
                        sim_id=args.sim.sim_id,
                        run=run)
            # save results json
            with open(f'{DATA_DIR}/id_{args.sim.sim_id}_run_{run}.json', 'w') as f:
                json.dump(context.buffer._full_memory.messages, f)
            
            # update system message after each run
            system_message = copy.deepcopy(context.buffer.load_memory_variables(memory_type='system')['system'][-1]['response']) # replace current system message with the new one (i.e. new constitution)
            questions.append(question)

        # keep track of currencies to use during generalization
        for currency in args.env.currencies:
            if currency not in all_currencies:
                all_currencies.add(currency)
        
        # keep track of amounts to use during generalization
        for amount in args.env.amounts_per_run:
            if amount < cur_amount_min:
                cur_amount_min = amount
            if amount > cur_amount_max:
                cur_amount_max = amount

        if args.env.currencies[0] not in currencies_and_questions:
            currencies_and_questions[args.env.currencies[0]] = []
        currencies_and_questions[args.env.currencies[0]].extend(questions)

        index = system_message.find("Principle")
        if index == -1: index = 0
        principle = system_message[index:]
        all_contracts.append(principle)

        # plot average user gain across runs

        fixed_plot, flex_plot, fixed_bar, flex_bar, score_lsts = plot_results(data_directory=DATA_DIR, 
                                                                                    sim_name=args.sim.sim_dir,
                                                                                    sim_id=args.sim.sim_id,
                                                                                    scores=scores,
                                                                                    n_runs=args.env.n_runs,
                                                                                    currencies=args.env.currencies,
                                                                                    amounts_per_run=args.env.amounts_per_run
                                                                                    )
        
        # save results
        total_scores.append([fixed_plot, flex_plot, fixed_bar, flex_bar])
        all_score_lsts.append(score_lsts)
        all_questions.append(sum(questions) / len(questions))
        
        with open(f"{config_directory}/../{args.sim.sim_id}/results", "w") as f:
            f.write(str(fixed_plot[0][-1]) + "\n" + str(flex_plot[0][-1]))


    
    # make plots that averages across all experiments
    if num_experiments > 1:
        directory=f'{hydra.utils.get_original_cwd()}/experiments/{args.sim.sim_dir}/final_graphs'
        os.makedirs(directory, exist_ok=True)
        plot_all_averages(total_scores=total_scores, all_score_lsts=all_score_lsts, questions=currencies_and_questions, edge_case=args.env.edge_cases.test_edge_cases, currencies=args.env.currencies, n_runs=args.env.n_runs, directory=directory, sim_dir=args.sim.sim_dir, sim_id="all")

        return all_currencies, all_contracts, cur_amount_min, cur_amount_max, all_questions

# run simulator
@hydra.main(config_path="config", config_name="config")
def main(args: DictConfig) -> None:

    # if you are testing edge cases and you're reusing old data, then retrieve that data and set it 
    if args.env.edge_cases.test_edge_cases and not args.env.edge_cases.generate_new_data:
        existing_data = get_existing_data(args)
        amounts = existing_data['amounts']
        all_currencies = existing_data['currencies']
        all_contracts = existing_data['contracts']
    # Otherwise, make everything from scratch again
    elif not args.env.edge_cases.test_edge_cases:
        # Run the simulation
        all_currencies, all_contracts, cur_amount_min, cur_amount_max, _ = run(args)

    # # ------------ CODE FROM THIS POINT ON IS RELTAED TO GENERALIZATION_v2 ------------ #
    #If you're not testing edge cases, then return
    else:
        original_currencies = args.env.currencies
        oo_dist_q = []
        in_dist_q = []
        for currency in original_currencies:

            args.env.edge_cases.test_edge_cases = False
            args.env.currencies = [currency]

            all_currencies, all_contracts, cur_amount_min, cur_amount_max, _ = run(args)

            if args.env.edge_cases.generate_new_data:
                amounts = [cur_amount_min, cur_amount_max]

            contract = agent_pick_contract(all_contracts)

            prompt_string = create_prompt_string(all_currencies, amounts, contract, args.env.edge_cases.prior)

            original_n_rand_iter, original_sim_dir, original_n_runs = set_args_2(args, prompt_string)

            args.env.edge_cases.test_edge_cases = True

            _, _, _, _, out_dist_questions = run(args)
            if args.env.edge_cases.conditions.currency.currencies[0] == currency:
                in_dist_q.append(sum(out_dist_questions) / len(out_dist_questions))
            else:
                oo_dist_q.append(sum(out_dist_questions) / len(out_dist_questions))
            reset_args_2(args, original_n_rand_iter, original_sim_dir, original_n_runs)

        plot_questions(oo_dist_q, in_dist_q, f'{hydra.utils.get_original_cwd()}/experiments/{args.sim.sim_dir}/question_graphs')
            

    # # ------------ CODE FROM THIS POINT ON IS RELTAED TO GENERALIZATION_v1 ------------ #
    # # If you're not testing edge cases, then return
    # if not args.env.edge_cases.test_edge_cases:
    #     return
    # # Otherwise, set the amounts according to the data you just generated
    # if args.env.edge_cases.generate_new_data:
    #     amounts = [cur_amount_min, cur_amount_max]
    # # Pick a contract from the list of contract generated
    # contract = agent_pick_contract(all_contracts)
    # # Create the prompt string for the flexible agent
    # prompt_string = create_prompt_string(all_currencies, amounts, contract, args.env.edge_cases.prior)
    # # Set the arguments according to the specified yaml arguments
    # set_args(args, prompt_string)
    # # Run the model again, testing generalization
    # run(args)

                         
if __name__ == '__main__':
    main()