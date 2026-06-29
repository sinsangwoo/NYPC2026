# 03_GAME_RULES.md (Part 1)

# NEXT NATION Developer Reference

### AI Development Manual (Part 1)

> This document is written for software engineers developing an autonomous AI player for the NYPC 2026 MASTER TRACK. It is **not** a copy of the official statement. Instead, it reorganizes the rules from an engineering perspective so they are easier to implement and reason about.

---

# 1. Purpose of the Game

NEXT NATION is a deterministic two-player turn-based strategy game.

Each player controls an autonomous AI agent.

The AI must continuously observe the current game state, choose actions, and react to the evolving battlefield.

Unlike ordinary programming contest problems, there is no single correct output.

The objective is to design a policy that consistently defeats another AI.

---

# 2. High-Level Objective

Each player owns exactly one Headquarters (HQ).

The primary objective is to destroy the opponent's HQ before your own HQ is destroyed.

If neither HQ is destroyed before the maximum number of turns, the remaining HQ health determines the winner.

If both HQs have equal health after the final turn, the game ends in a draw.

Everything else in the game—including economy, expansion, combat, and movement—exists only to achieve this objective.

---

# 3. Core Gameplay Loop

The game progresses for at most 200 turns.

Each turn follows the same lifecycle.

```
Receive current game state

↓

AI analyzes the state

↓

AI submits commands

↓

Game engine executes commands

↓

Game engine resolves combat

↓

Economy and upkeep are processed

↓

Updated game state is returned

↓

Repeat
```

The AI never directly modifies the world.

It only submits commands.

The game engine is the single source of truth.

---

# 4. Battlefield Overview

The battlefield consists of multiple connected regions.

Each region is treated as a node in a graph.

Connections between neighboring regions are provided at the beginning of the game.

Do NOT attempt to reconstruct connectivity from coordinates.

Always use the provided adjacency information.

Each region may contain:

* nothing
* warriors
* a Headquarters
* a Base
* a Stronghold that may later contain a Base

A region may contain warriors from both players simultaneously.

Combat occurs automatically after movement.

---

# 5. Symmetry

Every map is generated with point symmetry.

The left player and right player receive mirrored starting positions.

This means that:

* neither player has an inherent map advantage
* every strategy should assume symmetric opportunities
* evaluation functions should avoid left/right hardcoding whenever possible

---

# 6. Headquarters

Each player owns exactly one Headquarters.

The Headquarters:

* is the starting location
* trains new warriors
* generates income
* attacks enemies with its turret
* can be upgraded
* can be repaired
* must never be lost

Destroying the enemy Headquarters immediately wins unless both HQs are destroyed simultaneously.

---

# 7. Bases

Bases are economic buildings constructed on Strongholds.

Unlike Headquarters, Bases cannot train warriors.

Their purposes are:

* expanding territory
* increasing income
* providing defensive turret fire
* creating safe destinations for friendly movement

Because Bases affect economy over many turns, every construction decision has long-term consequences.

---

# 8. Warriors

Warriors are the only movable units.

Every warrior has:

* a unique identifier
* an owner
* current region
* current HP
* movement state
* destination (if moving)

Warriors execute orders automatically once a movement command has been issued.

They continue toward their destination until arrival.

The AI does not need to resend movement every turn.

---

# 9. Strongholds

Strongholds are special regions.

Only Strongholds may contain newly constructed Bases.

Not every region can be developed.

Therefore, Strongholds represent strategic economic resources.

Control of Strongholds often determines long-term economic strength.

---

# 10. Game Resources

The primary resource is Gold.

Gold is required for nearly every meaningful action.

Examples include:

* constructing Bases
* upgrading buildings
* repairing buildings
* training warriors
* issuing certain movement commands

Because Gold is limited, every action carries an opportunity cost.

A good AI should evaluate expected future value before spending Gold.

---

# 11. State Representation

From the perspective of an AI, the game is best represented as a world state.

```
GameState

├── Turn
├── Gold
├── Warriors
├── Buildings
├── Headquarters
├── Bases
├── Strongholds
├── Map
├── Movement Status
├── Building HP
├── Warrior HP
└── Remaining Countdown
```

The AI should never reason directly from raw input.

Instead, the parser should update a structured GameState object.

All strategic decisions should use this GameState.

---

# 12. AI Decision Philosophy

Every turn is fundamentally a resource allocation problem.

The AI continuously answers questions such as:

* Should Gold be saved or invested?
* Should more warriors be trained?
* Which Stronghold is worth expanding to?
* Which enemy position is most valuable to attack?
* Should damaged buildings be repaired?
* Should warriors defend or advance?

There is no universally correct answer.

The strength of the AI comes from selecting the best trade-off under the current circumstances.

---

# 13. Engineering Perspective

From a software engineering standpoint, the game should be viewed as four independent layers.

```
Game Engine

↓

Parser

↓

Game State

↓

Strategy

↓

Actions

↓

Output
```

Responsibilities must remain separated.

The parser reads data.

The GameState stores facts.

The Strategy makes decisions.

The emitter communicates with the engine.

Keeping these layers independent greatly simplifies testing, debugging, and future improvements.

---

# End of Part 1

The next section describes the detailed turn lifecycle, command system, movement mechanics, and state transitions that occur during every game turn.

# 03_GAME_RULES.md (Part 2)

# Turn Lifecycle & Command System

### AI Development Manual (Part 2)

---

# 14. Complete Turn Lifecycle

A single game lasts for at most **200 turns**.

Every turn follows exactly the same lifecycle.

The AI never executes game logic itself.

Instead, it only submits commands to the game engine.

The engine then updates the world according to the official rules.

The overall flow is:

```
Turn begins

↓

START command arrives

↓

AI reads current GameState

↓

AI decides actions

↓

AI submits COMMAND

↓

Morning Phase

↓

Day Phase

↓

Evening Phase

↓

Game Engine returns results

↓

AI updates GameState

↓

Next turn
```

Every decision must be made before the engine begins processing the turn.

---

# 15. Turn Input

Every turn begins with

```
START TURN T
```

where

* T is the current day number
* the first day is Turn 1
* the last possible day is Turn 200

Receiving START means:

"The previous turn has completely finished.
The current GameState is now fixed.
You may begin making decisions."

No game logic occurs until the AI submits its command list.

---

# 16. Command Phase

During the command phase the AI constructs a list of actions.

The command list is enclosed by

```
COMMAND
...
END
```

Only commands written between these two markers are executed.

The order of commands inside the list does not determine execution order.

The engine groups commands internally according to game rules.

Therefore,

```
MOVE

UPGRADE

TRAIN
```

produces the same execution order as

```
TRAIN

MOVE

UPGRADE
```

The engine always executes them according to the official phase sequence.

---

# 17. Available Commands

The AI can submit three types of commands.

## MOVE

```
MOVE WarriorID DestinationRegion
```

Example

```
MOVE A3 17
```

Meaning

* Warrior A3 receives a movement order.
* The destination becomes Region 17.
* The warrior continues traveling automatically until arrival.
* A new MOVE command cannot be issued while the warrior is already traveling.

---

## TRAIN

```
TRAIN n
```

Example

```
TRAIN 2
```

Meaning

Train two new warriors at the Headquarters.

Important constraints:

* At most one TRAIN command may exist in a turn.
* The requested number cannot exceed the Headquarters training capacity.
* Each trained warrior consumes Gold.

---

## UPGRADE

```
UPGRADE Region
```

If the specified region

contains

* an allied Headquarters
* an allied Base

the building is upgraded or repaired.

Otherwise,

if the region is a valid Stronghold,

a new Base is constructed.

Thus the same command has three possible meanings:

* Build
* Upgrade
* Repair

depending on the current state.

---

# 18. Morning Phase

After both players submit commands,

the Morning Phase begins.

Morning always consists of

```
Construction

↓

Movement

↓

Training
```

The order never changes.

This ordering has important strategic implications.

---

## Construction Stage

Every UPGRADE command is processed.

Possible outcomes:

* Build a new Base
* Upgrade an existing building
* Repair a max-level building

Construction immediately changes

* building level
* maximum HP
* current HP

Upgraded buildings become fully repaired.

---

## Movement Stage

Movement occurs after construction.

Every warrior currently traveling moves at most one region.

Warriors do NOT teleport.

Movement continues automatically over multiple turns.

If a warrior reaches its destination,

its movement state changes to Stationary.

---

Movement Blocking Rule

A warrior does not advance if enemies occupy its current region.

Combat must resolve first on later phases before movement can continue in future turns.

Therefore,

issuing a movement command does not guarantee progress every turn.

---

Movement Cost

Issuing a movement order may require Gold.

Moving toward an allied building is free.

Moving elsewhere costs Gold immediately when the command is accepted.

The payment is never refunded.

---

## Training Stage

Training occurs after movement.

New warriors always appear at the Headquarters.

Their maximum HP depends on the Headquarters level.

New warriors immediately receive unique IDs.

Warrior numbering always increases.

Numbers are never reused.

---

# 19. Day Phase

After all construction, movement, and training have completed,

combat begins automatically.

Players cannot submit any additional commands.

Combat is completely deterministic.

Every occupied region resolves combat independently.

The engine processes every region according to the same rules.

Combat consists of two sources of damage.

```
Turret attacks

↓

Warrior attacks
```

Destroyed objects are removed only after combat finishes.

Therefore,

a warrior reduced to zero HP during combat still participates in that combat round.

This detail is extremely important when implementing combat prediction.

---

# 20. Evening Phase

After combat,

the game enters the economic phase.

Evening always consists of

```
Labor

↓

Upkeep
```

---

## Labor Stage

Every surviving allied building generates Gold.

Income depends on

* building level
* number of friendly warriors stationed there

Each building has a maximum number of workers.

Additional warriors beyond the worker limit generate no additional income.

Therefore,

placing ten warriors on a level-one Base is usually wasteful.

---

## Upkeep Stage

After income,

every surviving warrior consumes Gold.

The engine processes warriors in ID order.

If insufficient Gold exists,

the warrior loses HP instead of paying maintenance.

If HP reaches zero,

the warrior retreats permanently.

This means economic collapse directly causes military collapse.

---

# 21. Turn Result

After the entire day finishes,

the engine reports everything that happened.

The AI receives sections describing

* upgraded buildings
* newly trained warriors
* warrior movement
* warrior damage
* building damage

The GameState must be updated only from these official results.

Never assume an action succeeded simply because it was submitted.

Always trust the engine output.

---

# 22. Engineering Notes

The AI should conceptually separate every turn into four stages.

```
Observe

↓

Evaluate

↓

Decide

↓

Synchronize
```

Observe

Read all information provided by the engine.

Evaluate

Estimate the current strategic situation.

Decide

Generate actions based only on the current GameState.

Synchronize

After receiving the engine results,

update every object inside GameState so that it exactly matches the official world state.

Failure to synchronize correctly causes accumulated state errors that become increasingly difficult to debug.

---

# End of Part 2

The next section introduces the detailed mechanics of buildings, Headquarters, Bases, upgrades, repairs, economy, and resource management, including how each building level affects long-term strategic strength.

# 03_GAME_RULES.md (Part 3)

# Buildings, Economy & Resource Management

### AI Development Manual (Part 3)

---

# 23. Buildings

Buildings are the permanent assets of a player.

Unlike warriors, buildings do not move.

However, they determine nearly every aspect of long-term strength.

Buildings provide:

* economic income
* defensive firepower
* safe destinations for movement
* map control

Losing buildings reduces future economic growth.

Protecting buildings is therefore an investment in future turns.

---

# 24. Building Types

The game contains two building categories.

## Headquarters (HQ)

Each player owns exactly one Headquarters.

Characteristics

* cannot be rebuilt
* can be upgraded
* can be repaired
* trains warriors
* produces income
* has a turret
* determines newly trained warrior HP

Destroying the Headquarters usually decides the game.

---

## Base

Bases are optional buildings.

Characteristics

* may only exist on Strongholds
* may be constructed at any time if conditions allow
* may be upgraded
* may be repaired
* generate income
* possess a defensive turret
* cannot train warriors

Bases represent long-term economic investments.

---

# 25. Building Ownership

Every building always belongs to exactly one player.

Buildings never change ownership.

If an enemy destroys a Base,

the Base disappears completely.

The attacker does NOT capture it.

To control that Stronghold again,

a completely new Base must later be constructed.

---

# 26. Building Placement

New Bases may only be constructed on Strongholds.

Construction additionally requires

* at least one allied warrior on that region
* no enemy warriors occupying that region

Both conditions must hold simultaneously.

Therefore,

simply reaching a Stronghold is not enough.

The AI must also secure temporary local superiority.

---

# 27. Building Levels

Buildings become stronger through upgrades.

An upgrade immediately

* increases maximum HP
* restores HP to maximum
* improves building capabilities

Because upgrades fully heal buildings,

sometimes upgrading is more valuable than repairing.

The AI should compare upgrade cost against repair cost before spending Gold.

---

# 28. Headquarters Progression

The Headquarters improves several independent attributes.

Increasing HQ level improves

* warrior maximum HP
* Headquarters HP
* turret damage
* training capacity
* worker capacity

These upgrades permanently improve every future turn.

Notice that only warriors trained AFTER an upgrade receive the increased HP.

Existing warriors keep their current HP.

This is an important strategic detail.

---

# 29. Base Progression

Base upgrades improve

* maximum HP
* turret strength
* worker capacity

Unlike Headquarters,

Base upgrades do NOT affect warriors.

Their primary value comes from

* stronger defense
* higher economic efficiency

---

# 30. Repairs

Once a building reaches its maximum level,

the UPGRADE command changes meaning.

Instead of increasing level,

it restores HP to maximum.

Repairs never increase statistics.

They only restore durability.

The AI should therefore distinguish between

```id="khjngm"
Upgrade

↓

Permanent improvement
```

and

```id="qvzccp"
Repair

↓

Temporary recovery
```

Although both use the same command,

their long-term value differs significantly.

---

# 31. Worker Capacity

Buildings generate income through workers.

Each building has a maximum worker capacity.

Income depends on

```id="lvrvvv"
minimum(

number of friendly warriors,

building worker capacity

)
```

Additional warriors beyond capacity contribute nothing.

Example

Level 1 Base

Worker Capacity = 1

Friendly Warriors = 5

Effective Workers = 1

Income = 15 Gold

The remaining four warriors provide no additional labor.

---

# 32. Labor Efficiency

From an optimization perspective,

placing warriors beyond worker capacity wastes military resources.

A stronger strategy often distributes workers across multiple productive buildings.

Rather than stacking ten warriors onto one Base,

placing them on several upgraded buildings usually produces higher income.

---

# 33. Gold

Gold is the central economic resource.

Almost every meaningful action requires Gold.

Typical expenses include

* Base construction
* Building upgrades
* Repairs
* Warrior training
* Certain movement commands

Gold therefore represents future flexibility.

Running out of Gold reduces the number of available strategic options.

---

# 34. Income Generation

Income occurs every Evening.

The engine evaluates every surviving allied building independently.

Each building contributes

```id="pnm28r"
15 × EffectiveWorkers
```

where

EffectiveWorkers is limited by worker capacity.

Destroyed buildings generate no income.

Enemy buildings never contribute.

Income from every building is summed,

then added to the player's Gold.

---

# 35. Upkeep

After income,

every surviving warrior consumes maintenance.

Maintenance is processed one warrior at a time.

If enough Gold exists,

the cost is paid normally.

Otherwise,

the warrior loses HP.

When HP reaches zero,

the warrior retreats permanently.

Economic collapse therefore directly translates into military losses.

---

# 36. Economic Snowball

NEXT NATION contains a strong economic snowball effect.

Earlier investments often generate larger long-term returns.

Example

```id="jvgscn"
Construct Base

↓

More Income

↓

More Gold

↓

More Warriors

↓

More Map Control

↓

Even More Income
```

Conversely,

falling behind economically often causes a chain reaction of weaker production, smaller armies, and reduced territorial control.

---

# 37. Opportunity Cost

Every purchase prevents another purchase.

Examples

Constructing a Base may delay

* training warriors

Repairing Headquarters may delay

* upgrading Headquarters

Training warriors may delay

* expanding territory

A strong AI should compare expected future value instead of evaluating each action independently.

---

# 38. AI Design Considerations

When evaluating economic decisions,

the strategy layer should estimate questions such as

* Will this Base repay its construction cost before Turn 200?
* Is upgrading this Base more valuable than training another warrior?
* Should Gold be saved for a Headquarters upgrade?
* Is repairing worthwhile if the building is unlikely to survive?
* Is the worker capacity currently saturated?

The strongest strategies evaluate investment over multiple future turns instead of maximizing immediate income.

---

# 39. Engineering Recommendations

Avoid scattering economic calculations throughout the codebase.

Instead,

implement a dedicated economic evaluation layer.

Example responsibilities

```id="dfeqah"
EconomyEvaluator

├── expected_income()

├── maintenance_cost()

├── building_roi()

├── worker_utilization()

├── can_afford()

└── future_gold_projection()
```

Separating economic reasoning from combat logic greatly improves maintainability and future experimentation.

---

# End of Part 3

The next section introduces the complete movement system, shortest-path behavior, automatic movement continuation, path blocking, and the combat resolution algorithm, which together form the tactical core of the game.

# 03_GAME_RULES.md (Part 4)

# Movement & Combat System

### AI Development Manual (Part 4)

---

# 40. Tactical Layer

Movement and combat form the tactical core of NEXT NATION.

Unlike economic decisions, these mechanics are executed automatically by the game engine.

The AI only issues intentions.

The engine determines exactly how units move and fight.

Therefore, a strong AI predicts future engine behavior rather than reacting after it happens.

---

# 41. Movement Orders

A movement order is issued by

```
MOVE WarriorID DestinationRegion
```

A movement order does **not** move the warrior immediately.

Instead, it assigns a destination.

The warrior will continue traveling toward that destination automatically over multiple turns.

Movement therefore behaves like a persistent state rather than a one-turn action.

---

# 42. Persistent Movement

After receiving a MOVE command, a warrior enters the **Moving** state.

While moving,

* the warrior remembers its destination,
* automatically advances every Morning,
* ignores future MOVE commands,
* exits the Moving state only after reaching its destination.

The AI does not need to resend the same MOVE command every turn.

Doing so is illegal because moving warriors cannot receive another movement order.

---

# 43. One-Step Movement

Movement speed is fixed.

Each Morning,

a moving warrior advances **at most one adjacent region**.

Even if the destination is very far away,

only one edge is traversed during a single turn.

Long-distance movement therefore requires multiple turns.

---

# 44. Shortest Path Rule

Movement is **not** chosen arbitrarily.

The engine always selects a path whose total geometric distance is minimal.

The sample code precomputes this information using Floyd-Warshall.

The resulting path remains fixed until the destination changes.

For performance,

the AI should precompute shortest paths during initialization rather than searching every turn.

---

# 45. Path Blocking

A moving warrior advances only if **no enemy warriors occupy its current region**.

If at least one enemy warrior is present,

movement is suspended.

The warrior remains in place until a future turn when the region becomes free of enemies.

This rule creates natural front lines.

Small defending forces can temporarily delay much larger armies simply by occupying the same region.

---

# 46. Movement Cost

Issuing a MOVE command may require Gold.

Destination is an allied building

→ Free

Destination is anywhere else

→ Costs Gold immediately

The payment occurs when the command is accepted,

not when the warrior actually arrives.

The Gold is never refunded.

Even if a Base is constructed later,

the original payment remains consumed.

---

# 47. Combat Overview

Combat occurs automatically during the Day Phase.

Players cannot interrupt or modify combat once commands have been submitted.

Every region resolves combat independently.

There is no interaction between different regions during combat.

---

# 48. Combat Order

Combat always follows the same sequence.

```
Turret Attacks

↓

Warrior Attacks

↓

Remove Destroyed Units

↓

Remove Destroyed Buildings
```

Understanding this ordering is essential for accurate combat prediction.

---

# 49. Turret Attacks

Every surviving building attacks first.

The number of attacks equals its turret attack value.

Each attack deals exactly one point of damage.

Multiple attacks simply repeat the targeting process.

Turret attacks never damage friendly units.

---

# 50. Warrior Attacks

Suppose

Friendly warriors = a

Enemy warriors = b

Then

Friendly side performs

a attacks.

Enemy side performs

b attacks.

Every surviving warrior contributes exactly one attack.

---

# 51. Simultaneous Resolution

Combat is effectively simultaneous.

A warrior reduced to zero HP during combat

does **not** disappear immediately.

Instead,

it continues participating until the entire combat phase finishes.

Example

```
3 vs 3

↓

One warrior reaches 0 HP

↓

That warrior still contributes its attack

↓

Combat finishes

↓

Only then is it removed
```

Ignoring this rule causes incorrect combat simulation.

---

# 52. Target Selection

Each attack always targets

the alive enemy warrior with

1. the lowest HP
2. if tied, the smallest warrior ID

This targeting rule is deterministic.

No randomness exists.

Therefore,

future combat outcomes are perfectly predictable.

---

# 53. Attacking Buildings

Buildings are attacked only when

no alive enemy warriors remain in that region.

As long as even one enemy warrior survives,

all attacks continue targeting warriors.

Only after every defending warrior reaches zero HP

may remaining attacks damage the building.

---

# 54. Building Damage

Each successful attack against a building removes exactly one HP.

Buildings never retaliate outside their normal turret attacks.

Destroyed buildings remain on the battlefield until combat finishes.

They disappear only after the entire combat phase ends.

---

# 55. Warrior Removal

After combat,

every warrior whose HP is zero or below

immediately retreats.

Retreated warriors

* never return,
* no longer consume upkeep,
* no longer generate labor,
* are removed permanently.

---

# 56. Building Removal

After combat,

every building whose HP reaches zero

is destroyed permanently.

Destroyed Bases disappear.

Destroyed Headquarters immediately determine victory according to the official win conditions.

---

# 57. Tactical Implications

Several strategic consequences follow from these mechanics.

Small defensive groups can delay advancing armies.

High-HP warriors naturally protect weaker warriors because attacks always focus on the lowest HP target.

Turrets become much stronger when combined with defending warriors because enemy attacks cannot reach the building until every defender has fallen.

Because combat is deterministic,

future battles can be simulated exactly before issuing commands.

This makes forward simulation one of the strongest techniques for building competitive AI.

---

# 58. Engineering Recommendation

Implement combat prediction as a separate simulation module rather than embedding combat logic inside the strategy layer.

Recommended structure

```
CombatSimulator

├── simulate_region()

├── simulate_day()

├── predict_losses()

├── predict_building_damage()

├── predict_survivors()

└── evaluate_attack()
```

A standalone simulator allows the AI to compare multiple candidate actions and choose the one with the highest expected long-term value.

---

# End of Part 4

The next section covers map generation, graph representation, shortest-path preprocessing, interaction protocol, parser implementation, and GameState synchronization.

# 03_GAME_RULES.md (Part 5)

# Engine Protocol, State Synchronization & Engineering Guidelines

### AI Development Manual (Final Part)

---

# 59. Engine Communication

NEXT NATION is an interactive programming contest.

Your program communicates continuously with the game engine through standard input and standard output.

The engine is authoritative.

The AI must never invent or assume information that has not been received from the engine.

Every decision should be based on the latest confirmed GameState.

---

# 60. Initialization Phase

The game begins with a READY message.

Initialization provides all information that never changes during the game.

Examples include

* player side
* map size
* region coordinates
* Stronghold locations
* graph connectivity

This information should be parsed exactly once.

Expensive preprocessing should also occur only once during initialization.

Typical preprocessing tasks include

* shortest path computation
* graph construction
* region indexing
* strategic map analysis

After initialization,

the AI must immediately output

```text
OK
```

within the initialization time limit.

---

# 61. Turn Protocol

Every game turn follows the same protocol.

```text
START

↓

AI Decision

↓

COMMAND

↓

END

↓

TURN Result

↓

GameState Update
```

The AI should never modify GameState before receiving official confirmation from the engine.

Commands express intention.

TURN describes reality.

Reality always wins.

---

# 62. Result Synchronization

The TURN message contains everything that actually happened.

Examples include

* completed construction
* successful training
* movement results
* warrior damage
* building damage

The local GameState should be synchronized exclusively using these official results.

Never infer success simply because a command was submitted.

---

# 63. FINISH

The engine may terminate the game immediately.

When

```text
FINISH
```

is received,

the program must terminate immediately.

Do not attempt to read further input.

Do not output additional commands.

Failure to terminate correctly may result in Wrong Answer.

---

# 64. Time Management

Two independent time limits exist.

Initialization

approximately one second.

Decision making

approximately one hundred milliseconds each turn.

Additionally,

the engine provides countdown buffers.

Occasional slow turns are acceptable,

but repeatedly exceeding the limit eventually results in Time Limit Exceeded.

The strategy should therefore prioritize predictable running time.

---

# 65. Map Representation

Although each battlefield is generated geometrically,

the AI should treat the battlefield as a graph.

Each region is a node.

Adjacency defines graph edges.

Coordinates exist primarily for visualization and shortest-path calculation.

Almost every strategic algorithm should operate on the graph rather than raw coordinates.

---

# 66. Strongholds

Strongholds are predetermined before the game begins.

Their locations never change.

Only Strongholds can contain newly constructed Bases.

Strongholds therefore represent permanent strategic resources.

One useful preprocessing step is ranking Strongholds according to

* travel distance
* defensive value
* expansion potential
* proximity to enemy territory

---

# 67. Recommended Internal Architecture

A maintainable implementation should separate responsibilities.

```text
Parser

↓

GameState

↓

Map

↓

PathFinder

↓

Economy Evaluator

↓

Combat Simulator

↓

Strategy

↓

Action Generator

↓

Output
```

Every module should have a single responsibility.

Keeping modules independent greatly simplifies debugging and experimentation.

---

# 68. Recommended Strategy Pipeline

A useful decision pipeline is

```text
Observe

↓

Update GameState

↓

Evaluate Economy

↓

Evaluate Combat

↓

Evaluate Expansion

↓

Score Candidate Actions

↓

Choose Best Plan

↓

Generate Commands
```

Separating evaluation from command generation allows different strategies to reuse the same infrastructure.

---

# 69. Common Implementation Mistakes

The following mistakes frequently produce incorrect behavior.

Ignoring automatic movement.

Assuming submitted commands always succeed.

Removing warriors immediately after reaching zero HP during combat.

Forgetting that buildings attack before warriors.

Allowing moving warriors to receive new movement commands.

Calculating income before combat.

Ignoring worker capacity.

Ignoring upkeep.

Failing to synchronize GameState after every TURN message.

Treating coordinates as graph connectivity.

Avoiding these mistakes eliminates many difficult-to-find bugs.

---

# 70. Determinism

NEXT NATION is highly deterministic.

Given the same

* map
* commands
* GameState

the engine always produces identical results.

This property enables

* forward simulation
* search algorithms
* heuristic evaluation
* Monte Carlo style planning
* minimax style planning

without uncertainty caused by random events.

---

# 71. Strategic Development Roadmap

Rather than attempting to build a perfect AI immediately,

development should proceed incrementally.

Suggested milestones

Stage 1

Correct parser.

Stage 2

Correct GameState synchronization.

Stage 3

Reliable shortest-path movement.

Stage 4

Economic expansion.

Stage 5

Combat prediction.

Stage 6

Rule-based strategic AI.

Stage 7

Evaluation-function tuning.

Stage 8

Forward simulation.

Stage 9

Search-based planning.

Stage 10

Tournament optimization.

Each stage builds upon the previous one.

Skipping foundational stages often leads to unstable behavior.

---

# 72. Philosophy

This contest is not primarily about implementing game rules.

The rules merely define the environment.

The real challenge is designing an autonomous decision-making system capable of

* allocating limited resources,
* predicting future states,
* balancing economy and military,
* adapting to an intelligent opponent,
* maximizing long-term advantage.

The strongest solutions are therefore not those with the most complicated code,

but those with the clearest architecture and the best strategic reasoning.

---

# 73. Final Notes

This document reorganizes the official specification from the perspective of AI software engineering.

The official statement remains the authoritative definition of the rules.

When uncertainty arises,

the implementation should always follow the official specification.

The purpose of this document is to provide an engineering-oriented reference that supports long-term development, debugging, testing, and strategic experimentation.

---

# End of Document

This concludes the developer-oriented rule reference for NEXT NATION.

Subsequent documentation should focus on software architecture, implementation details, testing methodology, and AI strategy rather than repeating the game rules.

