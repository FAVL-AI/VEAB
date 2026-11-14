"""Print the eight official EAI replay commands (does not execute)."""
for env in ('virtualhome','behavior'):
    for task in ('action_sequencing','transition_modeling','goal_interpretation','subgoal_decomposition'):
        print(f'eai-eval --dataset {env} --eval-type {task} --mode evaluate_results')
