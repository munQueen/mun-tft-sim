# import warnings
# warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas as pd 
import sqlite3
import random
import janitor
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

class GameManager:
    def __init__(self, crit_smoothing = False, *champs):
        self.champs = list(champs)
        self.crit_smoothing = crit_smoothing
        self.game_results = pd.DataFrame(columns=['damage', 'time', 'damage_type', 'was_attack_crit', 'target', 'sunder_flat', 'shred_flat', 'sunder_percent', 'shred_percent', 'magic_resist', 'armor', 'durability', 'effective_armor', 'effective_magic_resist', 'end_damage', 'seconds', 'total_damage', 'plot_label'])
        self.main_tank = []
        self.frontline = []
        self.backline = []
        #self.run_simulation()
        pass

    # now that the shiny app is calling this - probably shouldn't do the graphing
    # should just get all the data together so that it can be displayed in the app or wherever 

    def add_champ(self, champ):
        self.champs.append(champ)

    def run_simulation(self):
        for champ in self.champs:            
            champ.run_sim()
            champ.final_results["plot_label"] = champ.plot_label
            self.game_results = pd.concat([self.game_results, champ.final_results], ignore_index = True)
            # print(champ.final_results)
            
    def plot_results(self):
        sns.lineplot(x="seconds", y="total_damage", hue="plot_label", data=self.game_results)
        plt.show()

class Champion:
    def __init__(self, name, star_level, plot_label='', active_traits=[], active_items=[], crit_smoothing=False):
        # the misc things that keep the lights on 
        self.mana_on_attack = 10
        self.set_number = 12
        self.current_time = 0 
        self.mana_locked = False
        
        # loading in the arguments from the definition
        self.name = name
        self.crit_smoothing = crit_smoothing
        self.plot_label = plot_label
        self.star_level = star_level
        self.items = pd.read_csv("C:\\Users\\Jess\\code\\tft_sim\\data\\csvs\\items.csv")

        self.active_items = pd.DataFrame(columns=self.items.columns.values)  
        for item in active_items: 
            item_row = self.items.loc[self.items["item_full_name"] == item].copy()
            self.active_items = pd.concat([self.active_items, item_row], ignore_index=True)
        
        # self.active_items2 = self.items.query("item_full_name in @active_items")
        # print("active items:")
        # print(self.active_items)
        # print("active_items2:")
        # print(self.active_items2)
        self.spell = pd.read_csv("C:\\Users\\Jess\\code\\tft_sim\\data\\csvs\\spells.csv").query('@self.name == unit_name & @self.star_level == star_level')
        self.traits = pd.read_csv("C:\\Users\\Jess\\code\\tft_sim\\data\\csvs\\traits.csv")
        self.active_traits = self.traits.query("trait_id in @active_traits")

        #defining things that get used elsewhere
        self.events = pd.DataFrame(columns=['time', 'type'])
        self.stats = self.init_load_stats(name=self.name)
        self.buffs = pd.DataFrame(columns=['source', 'start_time', 'end_time', 'attack_damage', 'ability_power', 'attack_speed', 'crit_chance', 'crit_multiplier', 'damage_amp'])
        self.debuffs = pd.DataFrame(columns=['start_time', 'end_time', 'sunder_percent', 'sunder_flat', 'shred_percent', 'shred_flat', 'wound_percent', 'burn_percent'])            
        self.current_mana = self.stats.tail(1)["current_mana"].item()
        self.max_mana = self.stats.tail(1)["max_mana"].item()
        self.damage_tracking = pd.DataFrame(columns=['damage', 'time', 'damage_type', 'was_attack_crit', 'target'])
        
        

        self.on_attack_buffs = pd.DataFrame(columns=['source', 'duration', 'attack_damage', 'ability_power', 'attack_speed', 'crit_chance', 'crit_multiplier', 'damage_amp'])
        self.on_cast_effects = pd.DataFrame(columns=['source', 'duration', 'attack_damage', 'ability_power', 'attack_speed', 'crit_chance', 'crit_multiplier', 'damage_amp'])
        
        

        # hard code target stats, we'll rework it once it gets manually passed in 
        targets = {
            "target": ["main_tank", "frontline", "backline"], 
            "magic_resist": [80, 40, 20], 
            "armor": [80, 40, 20], 
            "durability": [.1, 0, 0]
        }
        self.targets = pd.DataFrame(data=targets)

        # each superfluous ability_can_crit_source increases crit damage by 10%
        # it > 1 means the ability can crit
        self.spell_can_crit = 0
        self.item_and_trait_buffs()


    def item_and_trait_buffs(self):
        # logic for any weird buffs from items and traits 
        # meant to be called at the end of the champion initialization  

        # mana on attack from scholars/shojins etc
        self.mana_on_attack += self.active_traits["mana_on_attack"].sum()

        for index, item in self.active_items.iterrows():            
            if item["item_id"] == 'rageblade':
                # for rageblade: add an on_attack_buff with infinite duration, that gives item_parameter_1 attackspeed
                rageblade_buff = {
                    "source": ["rageblade"],
                    "duration": [9999999], 
                    "attack_speed": [item.item_parameter_1]
                }
                self.on_attack_buffs = pd.concat([self.on_attack_buffs, pd.DataFrame(rageblade_buff)], ignore_index=True).fillna(0)
                pass

            # if item.item_id == 'nashors':
            #     pass

            # if item.item_id == 'blue':
            #     pass

            # if item.item_id == 'runaans':
            #     pass

            # if item.item_id == 'gs':
            #     pass

            # if item.item_id == 'gb':
            #     pass

        # abilities can crit from fist


        pass


    def calculate_current_stats(self):
        #1 get current stats from self.stats
        base_ability_power = self.stats.tail(1).ability_power.item()
        base_attack_damage = self.stats.tail(1).attack_damage.item()
        base_attack_speed = self.stats.tail(1).attack_speed.item()
        base_crit_chance = self.stats.tail(1).crit_chance.item()
        base_crit_multiplier = self.stats.tail(1).crit_multiplier.item()
        base_damage_amp = self.stats.tail(1).damage_amp.item()
        #2 get modifiers from buffs, traits, items

        # from the buffs data frame - get only rows where the current time is between start_time and end_time

        currently_active_buffs = self.buffs.loc[(self.current_time >= self.buffs["start_time"]) & (self.current_time < self.buffs["end_time"])]


        ability_power_modifiers = 0 + self.active_traits["flat_ability_power"].sum() + self.active_items["flat_ability_power"].sum() + currently_active_buffs["ability_power"].sum()
        attack_damage_modifiers = 1 
        attack_speed_modifiers = 1  + self.active_items["percent_attack_speed"].sum() + currently_active_buffs["attack_speed"].sum()
        crit_chance_modifiers = 0 
        crit_multiplier_modifiers = 0
        damage_amp_modifiers = 0 + self.active_traits["damage_amp"].sum() + self.active_items["damage_amp"].sum()

        

       

        #3 do the math for each stat 
        current_ability_power = base_ability_power + ability_power_modifiers
        current_attack_damage = base_attack_damage * attack_damage_modifiers
        current_attack_speed = base_attack_speed * attack_speed_modifiers
        current_crit_chance = base_crit_chance + crit_chance_modifiers
        current_crit_multiplier = base_crit_multiplier + crit_multiplier_modifiers
        current_damage_amp = base_damage_amp + damage_amp_modifiers

        current_stats = pd.Series(
            data = {
                "ability_power": current_ability_power, 
                "attack_damage": current_attack_damage, 
                "attack_speed": current_attack_speed, 
                "crit_chance": current_crit_chance, 
                "crit_multiplier": current_crit_multiplier, 
                "damage_amp": current_damage_amp
            }
        )
        
        return(current_stats)

    def init_load_stats(self, name):
        connection = sqlite3.connect("C:\\Users\\Jess\\code\\tft_sim\\data\\database\\community_dragon.db")
        cursor = connection.cursor()
        # open the database 
        query_sql = '''
        SELECT 
        name, 
        stats_attack_speed,
        stats_damage,
        100,
        stats_crit_chance, 
        stats_crit_multiplier,
        stats_initial_mana,
        stats_mana
        FROM champions
        where name == ?
        '''
        star_level_multiplier = 1 if self.star_level == 1 else 1.8 if self.star_level == 2 else 3.24 if self.star_level == 3 else 0
        # query the stats for just this unit 
        query_results = cursor.execute(query_sql, [name])
        results_tuple = query_results.fetchone()
        data = {
            "champion": [results_tuple[0]], 
            "attack_speed": [results_tuple[1]],
            "attack_damage": [results_tuple[2] * star_level_multiplier],
            "ability_power": [results_tuple[3]],
            "crit_chance": [results_tuple[4]],
            "crit_multiplier": [results_tuple[5]],
            "current_mana": [results_tuple[6]],
            "max_mana": [results_tuple[7]], 
            "damage_amp": [1],
            "time": [0]

        }
        
        return(pd.DataFrame(data=data))
    
    def run_sim(self, max_duration = 30000):
        while self.current_time <= max_duration: 
            self.find_next_event()
            self.process_next_event()
        self.final_results = self.damage_math()

        
        
    def attack(self):
        current_stats = self.calculate_current_stats()

        # was it a crit? 
        if random.random() < current_stats["crit_chance"]: 
            attack_is_crit = True
        else:
            attack_is_crit = False

        # how much damage did it deal
        if attack_is_crit == True:
            attack_damage = current_stats["attack_damage"] * current_stats["crit_multiplier"]
        else: 
            attack_damage = current_stats["attack_damage"]

        # print(current_stats["damage_amp"].item())
        attack_results = { 
            "damage": [attack_damage*current_stats["damage_amp"].item()], 
            "time": [self.current_time], 
            "damage_type": ["physical"], 
            "was_attack_crit": [attack_is_crit], 
            "target": ["main_tank"]
        }
        self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=attack_results)], ignore_index=True)
        self.current_mana += self.mana_on_attack  

        # handle what's going on in the on_attack_buffs df 
        for index, buff in self.on_attack_buffs.iterrows():
            attack_buff = {
                "source": [buff["source"]],
                "start_time": [self.current_time],
                "end_time": [buff["duration"] + self.current_time], 
                "attack_damage": [buff["attack_damage"]], 
                "ability_power": [buff["ability_power"]],
                "attack_speed": [buff["attack_speed"]], 
                "crit_chance": [buff["crit_chance"]],
                "crit_multiplier": [buff["crit_multiplier"]],
                "damage_amp": [buff["damage_amp"]]
            }

            self.buffs = pd.concat([self.buffs, pd.DataFrame(attack_buff)], ignore_index=True)

        


    def cast(self):
        # get current stats snapshot
        current_stats = self.calculate_current_stats()
        # subtract the current mana from max mana
        self.current_mana = self.current_mana - self.max_mana

        # logic for single target spells
        if "custom" in self.spell["tags"].item():
            pass
        
        if "buff" in self.spell["tags"].item():
            pass

        if "debuff" in self.spell["tags"].item():
            spell_debuff = {
                "target": [self.spell["debuff_target"].item()],
                "start_time": [self.current_time + self.spell["time_to_debuff"].item()], 
                "end_time": [self.current_time + self.spell["time_to_debuff"].item() +  self.spell["debuff_duration"].item()],
                "sunder_flat": [self.spell["sunder_flat"].item()], 
                "sunder_percent": [self.spell["sunder_percent"].item()], 
                "shred_flat": [self.spell["shred_flat"].item()], 
                "shred_percent": [self.spell["shred_percent"].item()], 
                "wound_percent": [self.spell["wound_percent"].item()], 
                "burn_percent": [self.spell["burn_percent"].item()]
            }
            self.debuffs = pd.concat([self.debuffs, pd.DataFrame(data=spell_debuff)], ignore_index=True)
            pass

        if "single_target" in self.spell["tags"].item():
            spell_base_damage = current_stats["ability_power"].item() * self.spell["single_target_ap_scaling"].item() + current_stats["attack_damage"].item() * self.spell["single_target_ad_scaling"].item()
            spell_damage = { 
                "damage": [spell_base_damage * current_stats["damage_amp"].item()], 
                "time": [self.current_time + self.spell["time_to_damage"].item()], 
                "damage_type": [self.spell["damage_type"].item()], 
                "was_attack_crit": [False], 
                "target": ["main_tank"]
            }

            self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=spell_damage)], ignore_index=True)


        if "adjacent_aoe" in self.spell["tags"].item():
            pass

        if "piercing_aoe" in self.spell["tags"].item():
            pass

        if "dot" in self.spell["tags"].item():
            pass



        # update the time for when being locked in the cast ends
        self.current_time += self.spell["animation_duration"].item()
        self.find_next_event()

        pass

    def champ_custom_cast(self):
        # placeholder
        # meant to be defined for each champ who has their own special logic
        pass

    def process_next_event(self): 
        # get the first row that hasn't happened yet from self.events 
        # buh lets just do get the first row to simplify 
        next_event_series = self.events.head(1)
        self.current_time = next_event_series["time"].item()
        if next_event_series["type"].item() == "attack": 
            self.attack()

        self.events.drop(self.events[self.events.time <= self.current_time].index, inplace=True)
        self.events.sort_values(by=["time"], inplace=True)
                    
        pass 

    def find_next_event(self):
        # what might the next event might be?
        # effect coming in (think adaptive helm mana)
        # buff wearing off changing stats

        # cast a spell
        if self.current_mana >= self.max_mana:
            # if a spell is about to be cast, then remove any future rows about attacking 
            # once the spell is done being cast we'll decide when the next attack should happen 
            self.events.drop(self.events[self.events["type"] == "attack"].index, inplace=True)
            self.cast()

                
        # attack

        # there should never be more than one attack queued up 
        # if there are any rows with time > current_time with type attack then don't add a new role
        current_stats = self.calculate_current_stats()
        #print(current_stats["attack_speed"].item())
        
        atk = {
            "time": [(round(1/current_stats["attack_speed"].item(), 3) * 1000) + self.current_time], 
            "type": ["attack"]
        } 
        self.events = pd.concat([self.events, pd.DataFrame(atk)], ignore_index=True) 
        

    def damage_math(self):
        # this function takes the raw damage recorded in self.damage_tracking and calculates armor/mr/shred

        # needs to make sure that, at any timestamp/damage_type/target combination, there's only one row 
        debuff_calcs_pt1 = (
        self.damage_tracking
            .merge(self.targets, how='left', left_on='target', right_on='target', suffixes=[None, '_t'])        
            .conditional_join(self.debuffs.rename(columns={'target': 'target_d'}),
                               ('time', 'start_time', '>='), ('time', 'end_time', '<'), ('target', 'target_d', '=='), how='left')
            [["time", "target", "magic_resist", "armor", "sunder_percent", "sunder_flat", "shred_percent", "shred_flat"]]
        )
    
        flat_debuffs = (
            debuff_calcs_pt1[["time", "target", "sunder_flat", "shred_flat"]]
                .groupby(["time", "target"])
                .sum()
                .fillna(0)
        )


        percent_debuffs = (
            debuff_calcs_pt1[["time", "target", "sunder_percent", "shred_percent"]]
                .groupby(["time", "target"])
                .max()
                .fillna(0)
        )    
                
        
        results = (
            self.damage_tracking
                .merge(flat_debuffs, how='left', on=['time', 'target'])
                .merge(percent_debuffs, how='left', on=['time', 'target'])
                .merge(self.targets, how='left', on ='target')
                .assign(effective_armor=lambda df: (df["armor"] - df["sunder_flat"]) * (1-df["sunder_percent"]))
                .assign(effective_magic_resist=lambda df: (df["magic_resist"] - df["shred_flat"]) * (1-df["shred_percent"]))
                .assign(end_damage=lambda df: df["damage"]) # just for true damage, we'll handle physical and magic below (more complex)
                .assign(seconds=lambda df: df["time"] / 1000)
        )

        # clean up any time effective armor/mr has gone below zero
        results["effective_armor"] = results["effective_armor"].where(results["effective_armor"] > 0, 0)
        results["effective_magic_resist"] = results["effective_magic_resist"].where(results["effective_magic_resist"] > 0, 0)
        # handle physical damage and true damage, respectively 
        # this is pretty clunky I don't like it 
        results["end_damage"] = results["end_damage"].where((results["damage_type"] == "physical") | (results["damage_type"] == "true"), results["damage"] * (1-results["effective_magic_resist"]/(results["effective_magic_resist"] + 100)))
        results["end_damage"] = results["end_damage"].where((results["damage_type"] == "magical") | (results["damage_type"] == "true"), results["damage"] * (1-results["effective_armor"]/(results["effective_armor"] + 100)))
        results["total_damage"] = results["end_damage"].cumsum()



        return(results)


g = GameManager()
 
g.add_champ(Champion(
        name='Zoe', 
        star_level = 2,        
        plot_label = "Zoe 2"
    )
)

g.add_champ(Champion(
        name='Zoe', 
        star_level = 2,        
        active_items=["Rabadon's Deathcap"],
        active_traits=["scholar_2"],
        plot_label = "Deathcap"
    ))

# g.add_champ(Champion(
#         name='Zoe', 
#         star_level = 2,
#         active_traits=["scholar_2"],
#         plot_label = "Zoe 2 w/Scholar 2"
#     ))

# g.add_champ(Champion(
#         name='Zoe', 
#         star_level = 2,
#         active_traits=["scholar_4"],
#         plot_label = "Zoe 2 w/Scholar 4"
#     )
# )

# g.add_champ(
#         Champion(
#         name='Zoe', 
#         star_level = 2,
#         active_traits=["scholar_2"],
#         plot_label = "No Items"
#     )
# )

# g.add_champ(
#         Champion(
#         name='Zoe', 
#         star_level = 2,
#         active_traits=["scholar_2"],
#         active_items=["rageblade"],
#         plot_label = "Rageblade"
#     )
# )

# g.run_simulation()
# g.plot_results()




# # # # TO DO 