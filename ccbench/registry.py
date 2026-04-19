"""Decorator registry for strategies, graders, corpus loaders.

Usage:

    from ccbench import strategy, grader

    @strategy("my_strategy")
    async def my_strategy(ctx, question, corpus):
        ...return a prompt string OR a full RunResult...

    @grader("my_grader")
    async def my_grader(ctx, question, answer):
        ...return dict with 'quality' key (0..1) at minimum...

A strategy returns either:
  - str           : a single-turn prompt (bench handles answer + judge)
  - RunResult     : for multi-turn / tool-use strategies that score themselves
"""
from __future__ import annotations
from typing import Callable, Dict


STRATEGIES: Dict[str, Callable] = {}
GRADERS: Dict[str, Callable] = {}
CORPUS_LOADERS: Dict[str, Callable] = {}


def strategy(name: str):
    def deco(fn):
        STRATEGIES[name] = fn
        return fn
    return deco


def grader(name: str):
    def deco(fn):
        GRADERS[name] = fn
        return fn
    return deco


def corpus_loader(name: str):
    def deco(fn):
        CORPUS_LOADERS[name] = fn
        return fn
    return deco
