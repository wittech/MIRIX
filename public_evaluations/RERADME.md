# The official code to run MIRIX


## LongMemEval Experiments



## LOCOMO Experiments
First download the dataset and run `mkdir results`. Then the file structure is as below:
```
main.py
agent.py
conversation_creatorr.py
README.md
data/
    locomo10.json
results/
.env
```

Also make sure to save the `OPENAI_API_KEY` in the file `.env`:
```
OPENAI_API_KEY=sk-xxxxxx
```
Then run the following command to generate the responses:
```
python main.py --agent_name mirix --dataset LOCOMO
```
After getting the outputs, we can use `evals.py` to generate the scores:
```
python evals.py --input_file results/mirix_LOCOMO --output_file results/mirix_LOCOMO/evaluation_metrics.json
```
