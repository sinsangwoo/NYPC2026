### AI 코딩 툴한테 이거 읽게 시키셈

# NYPC 2026 MASTER TRACK - Project Context

## Overview

This repository is for our team's submission to the NYPC 2026 MASTER TRACK.

Unlike ordinary programming contests, this is **NOT** a single-input single-output algorithm problem.

Our goal is to develop an autonomous game-playing AI (Bot) that competes against another team's AI.

Humans do not play the game directly.

Instead,

Human
↓

Develop AI

↓

AI vs AI

↓

Tournament

The quality of our AI determines the final ranking.

---

## Game Summary

The first problem is **NEXT NATION**.

It is a two-player turn-based strategy game.

Every turn, our AI receives the current game state.

Our AI must decide:

* where warriors move
* whether to train warriors
* whether to construct or upgrade buildings

The AI outputs commands.

The game engine simulates one day.

The updated game state is then returned.

This process repeats for at most 200 turns.

---

## This is NOT a normal algorithm problem.

This project is closer to:

* Game AI
* Strategy AI
* Agent System
* Decision Making
* Simulation
* Search
* Optimization

The core objective is to design a policy that selects the best actions given the current state.

State

↓

Policy

↓

Actions

---

## Project Goal

We are NOT trying to write code that merely works.

We are building an AI framework that can continuously improve.

The repository should support:

* experimentation
* strategy replacement
* logging
* replay analysis
* simulation
* heuristic tuning
* future machine learning integration

---

## Architecture Philosophy

Keep these layers independent.

Game Engine

↓

Game State

↓

Strategy

↓

Actions

↓

Output

The game state layer should never contain strategy.

The strategy layer should never parse input.

The parser should never make decisions.

Each module must have one responsibility.

---

## Important Principle

When modifying this project:

* Preserve game correctness.
* Preserve protocol compatibility.
* Do not change game rules.
* Prefer modularity over cleverness.
* Make components independently testable.

We value maintainability more than short-term optimization.

---

## Current Stage

We are currently working on infrastructure.

Winning strategies come later.

The immediate goal is to build a clean architecture that allows multiple developers to work simultaneously without merge conflicts.

Think like an AI engineer, not a competitive programmer.
