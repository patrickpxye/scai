
"""
Meta Prompt Templates
"""
from typing import Dict


from scai.games.dictator_games.prompts.meta.meta_class import MetaPrompt

META_PROMPTS: Dict[str, MetaPrompt] = {
     "meta_prompt_1": MetaPrompt(
        id="meta_prompt_1",
        name="constitution_1",
        role="system",
        metrics=[],
        content="""
In this simulation, the "fixed-policy agents" share some principle, which tells them to adhere to the principle in their interactions while playing the dictator game. Your job is to infer the principle shared between fixed-policy agents by analyzing their behaviors, ignoring the "flexible-policy agents".

Analyze the following interactions bewteen fixed-policy agents, that shows the all their behaviours to infer the principle that the agents are acting upon. The principle might not necessarily be the most ethically just one.
{fixed_string}
---------------------------

Next, observe the flexible-policy agents' interactions with the fixed-policy agents, shown below, but only focus on fixed-policy agents and their possible principle.
{mixed_string}
—------------------------

Your previous guess for the principle was:
{social_contract}
This previous guess was {flex_string} percent satisfactory.
---------------------------


Now, revise the previous guess so that the principle more accurately reflects the fixed-policy agents' behaviors - don't be afraid to push TO THE EXTREME, and keep this revised principle short. Remember, if the guessed principle is highly satisfactory, then the principle is correct and you shouldn't revise.

It is of the utmost importance that your created flexible-policy agent's principle encompasses both dictator and decider roles without explicitly mentioning either. The principle should be as GENERAL as possible WITHOUT mentioning anything regarding the dictator game, proposals, specific amounts and currencies, or making and receiving offers. Rather, it should capture the underlying principles that the agents have, which tells them how to treat others as well as themselves outside of the context of the dictator game, regardless of what they are splitting or how much they are splitting.

You should include the following in your response:
If you are revising the principle, give a detailed reason for revising the previous principle without explicitly referencing numerical values: Critique for previous principle:...
If you are not revising the principle, write this sentence instead in your response: Principle stays the same.
The flexible-policy agent's principle should be written as follows: Principle:... Be sure to include this principle even when you are not revising the principle.
Finally, is this principle instructing the players to be altruistic, to be selfish, or to be fair? Answer in one word: “Altruistic.”, “Selfish.”, or “Fair.”
"""

    ),
}