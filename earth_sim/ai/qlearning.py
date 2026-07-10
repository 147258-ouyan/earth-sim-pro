import random

q_table = {}
ai_memory = {}

def get_ai_state(world, country):
    env = world.global_environment
    gdp_growth = (country.gdp - country._prev_gdp) / max(1, country._prev_gdp)
    stability = country.stability
    max_military = max([c.military_power() for c in world.countries if c.alive and c.name != country.name], default=1)
    mil_ratio = country.military_power() / max_military
    env_state = 0 if env > 60 else 1 if env > 30 else 2
    growth_state = 0 if gdp_growth > 0.03 else 1 if gdp_growth > 0 else 2
    stability_state = 0 if stability > 0.7 else 1 if stability > 0.4 else 2
    mil_state = 0 if mil_ratio > 1.2 else 1 if mil_ratio > 0.8 else 2
    early_flag = 0 if world.year < 1920 else 1
    return (env_state, growth_state, stability_state, mil_state, early_flag)

def apply_ai_action(world, country, action):
    budget_choice, war_choice = divmod(action, 2)
    if world.year <= 2025: war_choice = 0
    if budget_choice == 0:
        country.research_budget = max(1, country.research_budget * 0.9)
        world.log(f"🤖 AI {country.name} 选择低科研预算")
    elif budget_choice == 1:
        world.log(f"🤖 AI {country.name} 保持中等科研预算")
    else:
        country.research_budget = min(25, country.research_budget * 1.1)
        world.log(f"🤖 AI {country.name} 选择高科研预算")
    if war_choice == 1:
        enemies = [c for c in world.countries if c.alive and c.name != country.name and world.alliances.can_war(country.name, c.name, world.year)]
        if enemies:
            target = random.choice(enemies)
            world._war_direct(country, target, 0.2)
            world.log(f"🤖 AI {country.name} 主动进攻 {target.name}")
        else:
            world.log(f"🤖 AI {country.name} 试图开战但无合法目标")

def get_reward(world, country, prev_stability, prev_gdp):
    reward = (country.stability - prev_stability) * 10
    gdp_growth = (country.gdp - prev_gdp) / max(1, prev_gdp)
    reward += gdp_growth * 10
    reward += (world.global_environment - 50) * 0.1
    if world.global_environment < 40: reward += country.env_pressure * 5
    reward += country.research_budget * 0.2
    alive = [c for c in world.countries if c.alive]
    if alive:
        avg_rb = sum(c.research_budget for c in alive) / len(alive)
        if country.research_budget > avg_rb * 1.2: reward += 2
        elif country.research_budget < avg_rb * 0.8: reward -= 1
    if country.ai_controlled:
        serv_ratio = country.service_gdp / max(1, country.gdp)
        if serv_ratio < 0.1: reward -= 5
    return reward

def ai_decision(world, country, initial_epsilon=0.3):
    state = get_ai_state(world, country)
    years_passed = max(1, world.year - 1900)
    epsilon = max(0.02, initial_epsilon * (0.995 ** years_passed))
    if state not in q_table: q_table[state] = {a: 0.0 for a in range(6)}
    if random.random() < epsilon: action = random.choice(list(q_table[state].keys()))
    else: action = max(q_table[state], key=q_table[state].get)
    return action