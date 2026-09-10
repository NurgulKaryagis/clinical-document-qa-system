import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    ContextPrecisionWithoutReference,
    ContextRecall,
    Faithfulness,
)

load_dotenv()

FAITHFULNESS_THRESHOLD = 0.85

@dataclass
class RagasResult:
    passed: bool
    score: float
    

def build_llm(
    model="gpt-4o-mini",
    api_key=None,
    ):
    api_key = api_key or os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=api_key)
    llm = llm_factory(model=model, client=client)
    return llm


async def faithfulness_score(
    user_input: str,
    response: str,
    retrieved_context: list[str]
    ) -> float :
    faithfulness_metric = Faithfulness(llm=build_llm())
    result = await faithfulness_metric.ascore(user_input=user_input, response=response, retrieved_contexts=retrieved_context)
    return result.value

def faithfulness_mean(
    score_list: list[float],
    threshold: float = FAITHFULNESS_THRESHOLD
    )-> RagasResult :
    average = sum(score_list) / len(score_list)
    return RagasResult(
        passed= average >= threshold ,
        score= average    
    )
    
async def context_precision_wo_reference_score(
    user_input: str,
    response: str,
    retrieved_context: list[str]
    ) -> float :
    context_precision_wo_reference_metric = ContextPrecisionWithoutReference(llm=build_llm())
    result = await context_precision_wo_reference_metric.ascore(user_input=user_input, response=response, retrieved_contexts=retrieved_context)
    return result.value

def context_precision_wo_reference_mean(
    score_list: list[float],
    )-> float :
    average = sum(score_list) / len(score_list)
    return average

async def context_recall_score(
    user_input: str,
    retrieved_context: list[str],
    reference: str
    ) -> float :
    context_recall_metric = ContextRecall(llm=build_llm())
    result = await context_recall_metric.ascore(user_input=user_input, retrieved_contexts=retrieved_context, reference=reference)
    return result.value

def context_recall_mean(
    score_list: list[float],
    )-> float :
    average = sum(score_list) / len(score_list)
    return average