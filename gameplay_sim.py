# import warnings
# warnings.simplefilter(action='ignore', category=FutureWarning)
from pathlib import Path

import pandas as pd 
import random
import janitor
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

app_dir = Path(__file__).parent

class GameManager:
    def __init__(self, set=13, patch='new', sim_duration=30000, *champs):
        self.champs = list(champs)
        self.game_results = pd.DataFrame(columns=['time', 'seconds', 'damage_type', 'end_damage', 'plot_label', 'end_damage_smooth_crit', 'end_damage_rng_crit', 'total_damage_smooth_crit', 'total_damage_rng_crit'])
        self.main_tank = []
        self.frontline = []
        self.backline = []        
        self.sim_duration = sim_duration
        pass


    def add_champ(self, champ):
        self.champs.append(champ)

    def run_simulation(self, targets, adjacent_unit_count=2, backline_target_count=1):
        for champ in self.champs:            
            print(champ.stats)
            champ.run_sim(max_duration=self.sim_duration, targets=targets, adjacent_unit_count=adjacent_unit_count)
            champ.final_results["plot_label"] = champ.plot_label
            self.game_results = pd.concat([self.game_results, champ.final_results], ignore_index = True)
        print(self.game_results)
            
    def plot_results(self):
        sns.lineplot(x="seconds", y="total_damage_rng_crit", hue="plot_label", data=self.game_results)
        plt.show()

class Champion:
    def __init__(self, name, star_level, set_number=13, patch='new', plot_label='', active_traits=[], active_items=[], crit_smoothing=False, adjacent_unit_count=2, backline_target_count=1):
        # the misc things that keep the lights on 
        self.mana_on_attack = 10
        self.set_number = set_number
        self.current_time = 0 
        self.mana_locked = False
        
        # loading in the arguments from the definition
        self.name = name
        self.crit_smoothing = crit_smoothing
        self.plot_label = plot_label
        self.star_level = star_level
        self.items = pd.read_csv(app_dir/"data/csvs/items.csv")

        self.active_items = pd.DataFrame(columns=self.items.columns.values)  
        for item in active_items: 
            item_row = self.items.loc[self.items["item_full_name"] == item].copy()
            self.active_items = pd.concat([self.active_items, item_row], ignore_index=True)
        self.spell = pd.read_csv(app_dir/"data/csvs/spells.csv").query('@self.name == unit_name & @self.star_level == star_level')
        self.traits = pd.read_csv(app_dir/"data/csvs/traits.csv")
        self.active_traits = self.traits.query("ui_name in @active_traits")

        #defining things that get used elsewhere
        self.events = pd.DataFrame(columns=['time', 'type'])
        self.stats = self.init_load_stats(name=self.name)
        # potential refactor - change to base stats and make a series not a df 
        self.time_based_buffs = pd.DataFrame(columns=['source', 'start_time', 'end_time', 'attack_damage', 'ability_power', 'attack_speed', 'crit_chance', 'crit_multiplier', 'damage_amp'])
        self.empowered_autos = pd.DataFrame(columns=['source', 'number_of_autos', 'bonus_damage', 'bonus_damage_type', 'bonus_crit_chance', 'is_guaranteed_crit'])

        self.debuffs = pd.read_csv(app_dir/"data/csvs/debuffs_structure.csv")
        #self.debuffs = pd.DataFrame(columns=['debuff_target', 'start_time', 'end_time', 'sunder_percent', 'sunder_flat', 'shred_percent', 'shred_flat', 'wound_percent', 'burn_percent'])            
        self.debuffs = self.debuffs.astype({'start_time': 'float64', 'end_time': 'float64'})
        self.current_mana = self.stats.tail(1)["current_mana"].item()
        self.max_mana = self.stats.tail(1)["max_mana"].item()
        self.damage_tracking = pd.DataFrame(columns=['source', 'base_damage', 'time', 'damage_type', 'was_attack_crit', 'crit_chance', 'crit_multiplier', 'target'])
        
        

        self.on_attack_buffs = pd.DataFrame(columns=['source', 'duration', 'attack_damage', 'ability_power', 'attack_speed', 'crit_chance', 'crit_multiplier', 'damage_amp', 'stacking_type'])
        self.on_cast_buffs = pd.DataFrame(columns=['source', 'duration', 'attack_damage', 'ability_power', 'attack_speed', 'crit_chance', 'crit_multiplier', 'damage_amp', 'stacking_type'])
        
        # these will be replaced by calls in 
        self.adjacent_unit_count = adjacent_unit_count
        self.backline_target_count = backline_target_count

        # hard code target stats, we'll rework it once it gets manually passed in 
        targets = {
            "target": ["main_tank", "frontline", "backline"], 
            "magic_resist": [69, 40, 20], 
            "armor": [69, 40, 20], 
            "durability": [.1, 0, 0]
        }
        self.targets = pd.DataFrame(data=targets)

        # each superfluous ability_can_crit_source increases crit damage by 10%
        # it > 1 means the ability can crit
        self.spell_can_crit_sources = 0
        self.item_and_trait_buffs()

        self.times_cast = 0 
        self.times_attacked = 0

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
                    "attack_speed": [item.item_parameter_1], 
                    "stacking_type": "stacks"
                }
                self.on_attack_buffs = pd.concat([self.on_attack_buffs, pd.DataFrame(rageblade_buff)], ignore_index=True).fillna(0)
                

            if item.item_full_name == "Nashor's Tooth":
                nashors_buff = {
                    "source": ["nashors"],
                    "duration": [item.item_parameter_2], 
                    "attack_speed": [item.item_parameter_1], 
                    "stacking_type": "refreshes"
                }
                self.on_cast_buffs = pd.concat([self.on_cast_buffs, pd.DataFrame(nashors_buff)], ignore_index=True).fillna(0)


            if item.item_full_name == "Archangel's Staff":                
                aa_df = pd.DataFrame()
                aa_df["start_time"] = pd.Series(np.arange(5000, 100000, 5000))
                aa_df["source"] = pd.Series("archangel's", index=range(len(aa_df)))
                aa_df["ability_power"] = pd.Series(30, index=range(len(aa_df)))
                aa_df["end_time"] = pd.Series(999999, index=range(len(aa_df)))
                self.time_based_buffs = pd.concat([self.buffs, aa_df], ignore_index=True)
            
            if item.item_id == 'blue':
                pass

            if item.item_id == 'runaans':
                pass

            if item.item_id == 'gs':
                pass

            if item.item_id == 'gb':
                pass

            self.spell_can_crit_sources += item.spell_can_crit
            self.current_mana += item.flat_mana
        
        # this is at the end of all items & traits 
        if self.spell_can_crit_sources > 1:
            self.stats["crit_multiplier"] = self.stats["crit_multiplier"] + (self.spell_can_crit_sources - 1) * 0.10

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

        currently_active_buffs = self.time_based_buffs.loc[(self.current_time >= self.time_based_buffs["start_time"]) & (self.current_time < self.time_based_buffs["end_time"])]


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
        champs = pd.read_csv(app_dir/"data/csvs/champions.csv")
        results = champs.loc[champs.champion == name].copy()
        return(results)
    
    def run_sim(self, targets, max_duration = 30000, adjacent_unit_count = 2):
        self.adjacent_unit_count = adjacent_unit_count
        self.targets = targets
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

        attack_results = { 
            "source": "attack",
            "base_damage": [current_stats["attack_damage"].item()*current_stats["damage_amp"].item()], 
            "time": [self.current_time], 
            "damage_type": ["physical"], 
            "was_attack_crit": [attack_is_crit], 
            "crit_chance": [current_stats["crit_chance"].item()], 
            "crit_multiplier": [current_stats["crit_multiplier"].item()],
            "target": ["main_tank"]
        }
        self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=attack_results)], ignore_index=True)
        self.current_mana += self.mana_on_attack  


        # iteratre through on_attack_buffs to add in any new buffs as a result of this attack
        for index, buff in self.on_attack_buffs.iterrows():
            if buff["stacking_type"] == "refreshes":
            # remove all rows in self.buffs with the same source, then add a new row in 
                self.time_based_buffs = self.time_based_buffs.loc[self.time_based_buffs["source"] != buff["source"]].copy()
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

            self.time_based_buffs = pd.concat([self.buffs, pd.DataFrame(attack_buff)], ignore_index=True)
            self.times_attacked += 1 

    def cast(self):

        # get current stats snapshot
        current_stats = self.calculate_current_stats()

        # subtract the current mana from max mana
        self.current_mana = self.current_mana - self.max_mana


        # logic for single target spells
        if "custom" in self.spell["tags"].item():            
            # Lux 13 - add a row to self.empowered_auto for 1 empowered auto, using self.spell.custom_ap_ratio_1 for the bonus magic damage
            if self.name == "Lux" & self.set_number == 13:
                pass

            # Powder 13 - needs custom input for how many units to hit at 33% reduced and 66% reduced damage, using custom_ap_ratio_1 for damage
            # Draven 13 - GULP 
            # Maddie 13 - let's just assume they all go into the amin tank for now
            if self.name == "Maddie" & self.set_number == 13: 
                spell_base_damage = current_stats["ability_power"].item() * self.spell["single_target_ap_scaling"].item() + current_stats["attack_damage"].item() * self.spell["single_target_ad_scaling"].item()
                one_maddie_shot = {
                    "source": "spell",
                    "base_damage": [spell_base_damage * current_stats["damage_amp"].item()], 
                    "time": [self.current_time + self.spell["time_to_damage"].item()], 
                    "damage_type": [self.spell["damage_type"].item()], 
                    "was_attack_crit": [False], 
                    "crit_chance": current_stats["crit_chance"].item(),
                    "crit_multiplier": current_stats["crit_multiplier"].item(),
                    "target": ["main_tank"]
                }
                for i in range(6):
                    self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=one_maddie_shot)], ignore_index=True)
        if "debuff" in self.spell["tags"].item():
            spell_debuff = {
                "debuff_target": [self.spell["debuff_target"].item()],
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
                "source": "spell",
                "base_damage": [spell_base_damage * current_stats["damage_amp"].item()], 
                "time": [self.current_time + self.spell["time_to_damage"].item()], 
                "damage_type": [self.spell["damage_type"].item()], 
                "was_attack_crit": [False], 
                "crit_chance": current_stats["crit_chance"].item(),
                "crit_multiplier": current_stats["crit_multiplier"].item(),
                "target": ["main_tank"]
            }
            self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=spell_damage)], ignore_index=True)
        if "target_and_adjacent_aoe" in self.spell["tags"].item():
            # essentially running both the logic for single_target and adjacent_aoe
            spell_base_damage = current_stats["ability_power"].item() * self.spell["adjacent_aoe_ap_scaling"].item() + current_stats["attack_damage"].item() * self.spell["adjacent_aoe_ad_scaling"].item()
            for i in range(self.adjacent_unit_count):
                spell_damage = { 
                    "source": "spell",
                    "base_damage": [spell_base_damage * current_stats["damage_amp"].item()], 
                    "time": [self.current_time + self.spell["time_to_damage"].item()], 
                    "damage_type": [self.spell["damage_type"].item()], 
                    "was_attack_crit": [False], 
                    "crit_chance": current_stats["crit_chance"].item(),
                    "crit_multiplier": current_stats["crit_multiplier"].item(),
                    "target": ["frontline"]
                }
                self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=spell_damage)], ignore_index=True)    
            spell_damage = { 
                "source": "spell",
                "base_damage": [spell_base_damage * current_stats["damage_amp"].item()], 
                "time": [self.current_time + self.spell["time_to_damage"].item()], 
                "damage_type": [self.spell["damage_type"].item()], 
                "was_attack_crit": [False], 
                "crit_chance": current_stats["crit_chance"].item(),
                "crit_multiplier": current_stats["crit_multiplier"].item(),
                "target": ["main_tank"]
            }

            self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=spell_damage)], ignore_index=True)
            pass    
        if "adjacent_aoe" in self.spell["tags"].item():
            spell_base_damage = current_stats["ability_power"].item() * self.spell["adjacent_aoe_ap_scaling"].item() + current_stats["attack_damage"].item() * self.spell["adjacent_aoe_ad_scaling"].item()
            for i in range(self.adjacent_unit_count):
                spell_damage = { 
                    "source": "spell",
                    "base_damage": [spell_base_damage * current_stats["damage_amp"].item()], 
                    "time": [self.current_time + self.spell["time_to_damage"].item()], 
                    "damage_type": [self.spell["damage_type"].item()], 
                    "was_attack_crit": [False], 
                    "crit_chance": current_stats["crit_chance"].item(),
                    "crit_multiplier": current_stats["crit_multiplier"].item(),
                    "target": ["frontline"]
                }
                self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=spell_damage)], ignore_index=True)                            
            pass 
        if "piercing_aoe" in self.spell["tags"].item():
            # initialize the scaling modifier at 1 
            # after each damage, multiply it by the 
            ap_piercing_modifier = 1 
            ad_piercing_modifier = 1
                        
            # the piercing aoe hits the MAIN TARGET first
            spell_base_damage = (ap_piercing_modifier * current_stats["ability_power"].item() * self.spell["piercing_aoe_ap_ratio"].item()) + (ad_piercing_modifier *current_stats["attack_damage"].item() * self.spell["piercing_aoe_ad_ratio"].item())
            spell_damage = { 
                    "source": "spell",
                    "base_damage": [spell_base_damage * current_stats["damage_amp"].item()], 
                    "time": [self.current_time + self.spell["time_to_damage"].item()], 
                    "damage_type": [self.spell["damage_type"].item()], 
                    "was_attack_crit": [False], 
                    "crit_chance": current_stats["crit_chance"].item(),
                    "crit_multiplier": current_stats["crit_multiplier"].item(),
                    "target": ["main_tank"]
                }
            self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=spell_damage)], ignore_index=True)                         
            ap_piercing_modifier = ap_piercing_modifier * self.spell["piercing_aoe_ap_scaling"].item()
            ad_piercing_modifier = ad_piercing_modifier * self.spell["piercing_aoe_ad_scaling"].item()
            # then: iterate over the FRONTLINE TARGETS 
            for i in range(self.adjacent_unit_count):
                spell_base_damage = (ap_piercing_modifier * current_stats["ability_power"].item() * self.spell["piercing_aoe_ap_ratio"].item()) + (ad_piercing_modifier *current_stats["attack_damage"].item() * self.spell["piercing_aoe_ad_ratio"].item())
                spell_damage = { 
                        "source": "spell",
                        "base_damage": [spell_base_damage * current_stats["damage_amp"].item()], 
                        "time": [self.current_time + self.spell["time_to_damage"].item()], 
                        "damage_type": [self.spell["damage_type"].item()], 
                        "was_attack_crit": [False], 
                        "crit_chance": current_stats["crit_chance"].item(),
                        "crit_multiplier": current_stats["crit_multiplier"].item(),
                        "target": ["frontline"]
                    }
                self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=spell_damage)], ignore_index=True)      
                                          
                ap_piercing_modifier = ap_piercing_modifier * self.spell["piercing_aoe_ap_scaling"].item()
                ad_piercing_modifier = ad_piercing_modifier * self.spell["piercing_aoe_ad_scaling"].item()
            # then: iterate over the FRONTLINE TARGETS 
            for i in range(self.backline_target_count):
                spell_base_damage = (ap_piercing_modifier * current_stats["ability_power"].item() * self.spell["piercing_aoe_ap_ratio"].item()) + (ad_piercing_modifier *current_stats["attack_damage"].item() * self.spell["piercing_aoe_ad_ratio"].item())
                spell_damage = { 
                        "source": "spell",
                        "base_damage": [spell_base_damage * current_stats["damage_amp"].item()], 
                        "time": [self.current_time + self.spell["time_to_damage"].item()], 
                        "damage_type": [self.spell["damage_type"].item()], 
                        "was_attack_crit": [False], 
                        "crit_chance": current_stats["crit_chance"].item(),
                        "crit_multiplier": current_stats["crit_multiplier"].item(),
                        "target": ["backline"]
                    }
                self.damage_tracking = pd.concat([self.damage_tracking, pd.DataFrame(data=spell_damage)], ignore_index=True)                                
                ap_piercing_modifier = ap_piercing_modifier * self.spell["piercing_aoe_ap_scaling"].item()
                ad_piercing_modifier = ad_piercing_modifier * self.spell["piercing_aoe_ad_scaling"].item()

            # then: iterate over the BACKLINE TARGETS 
        if "dot" in self.spell["tags"].item():
            pass
        
        if "retarget" in self.spell["tags"].item():
            # for RETARGET - probably want to refactor how targets work? 
            # it would be pretty cool to have a DF with one row per target 
            pass 


        for index, buff in self.on_cast_buffs.iterrows():
            if buff["stacking_type"] == "refreshes":
                # remove all rows in self.buffs with the same source, then add a new row in 
                self.time_based_buffs = self.time_based_buffs.loc[self.time_based_buffs["source"] != buff["source"]].copy()
            cast_buff = {
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

            self.time_based_buffs = pd.concat([self.buffs, pd.DataFrame(cast_buff)], ignore_index=True)

        # update the time for when being locked in the cast ends
        self.current_time += self.spell["animation_duration"].item()
        self.times_cast += 1
        self.find_next_event()

        

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
        
        atk = {
            "time": [(round(1/current_stats["attack_speed"].item(), 3) * 1000) + self.current_time], 
            "type": ["attack"]
        } 
        self.events = pd.concat([self.events, pd.DataFrame(atk)], ignore_index=True) 
        
    def damage_math(self):
        print("debugging: this is what self.damage_tracking looks like")
        print(self.damage_tracking)
        # this function takes the raw damage recorded in self.damage_tracking and calculates armor/mr/shred

        # needs to make sure that, at any timestamp/damage_type/target combination, there's only one row 
        debuff_calcs_pt1 = (
        self.damage_tracking
            .merge(self.targets, how='left', left_on='target', right_on='target', suffixes=[None, '_t'])        
            .conditional_join(self.debuffs,
                               ('time', 'start_time', '>='), ('time', 'end_time', '<'), ('target', 'debuff_target', '=='), how='left')
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
                .assign(end_damage=lambda df: df["base_damage"]) # just for true damage, we'll handle physical and magic below (more complex)
                .assign(seconds=lambda df: df["time"] / 1000)
        )

        # clean up any time effective armor/mr has gone below zero
        results["effective_armor"] = results["effective_armor"].where(results["effective_armor"] > 0, 0)
        results["effective_magic_resist"] = results["effective_magic_resist"].where(results["effective_magic_resist"] > 0, 0)
        # handle physical damage and true damage, respectively 
        # this is pretty clunky I don't like it 


        # pandas where - if it's true, keep the original value, if it's false, then do what's in the logic 
        results["end_damage"] = results["end_damage"].where((results["damage_type"] == "physical") | (results["damage_type"] == "true"), results["base_damage"] * (1-results["effective_magic_resist"]/(results["effective_magic_resist"] + 100)))
        results["end_damage"] = results["end_damage"].where((results["damage_type"] == "magical") | (results["damage_type"] == "true"), results["base_damage"] * (1-results["effective_armor"]/(results["effective_armor"] + 100)))

        results["can_spell_crit"] = min(1, self.spell_can_crit_sources)

        print("in damage_math(), pre-aggregation:")
        print(results)

        # we need to aggregate the end_damage at the time level
        # including crit_chance, crit_multiplier, spell_crit?
        aggregated_damage = results.groupby(by=["time", "source", "damage_type"]).sum().reset_index()[["time", "source", "damage_type",  "end_damage"]]
        crit_stats = results[["time", "source", "crit_chance", "crit_multiplier", "can_spell_crit"]].drop_duplicates()

        final_results = pd.merge(
            left=aggregated_damage, 
            right=crit_stats,
            how='left', 
            on=["time", "source"]

        )

        final_results["crit_rng"] = np.random.default_rng().random(len(final_results))
        
        # first calculate the damage if it was a crit
        # then use .where() to handle cases which didn't crit 
        final_results["end_damage_smooth_crit"] = final_results["end_damage"] + (final_results["crit_chance"] *(final_results["crit_multiplier"]-1) * final_results["end_damage"])
        final_results["end_damage_smooth_crit"] = final_results["end_damage_smooth_crit"].where(~((final_results["source"] == "spell") & (final_results["can_spell_crit"] == 0)), final_results["end_damage"])


        final_results["end_damage_rng_crit"] = final_results["end_damage"] * final_results["crit_multiplier"]
        # use where to set the cases where crit_rng was higher than crit_chance back to base damage
        final_results["end_damage_rng_crit"] = final_results["end_damage_rng_crit"].where(~(final_results["crit_rng"] > final_results["crit_chance"]), final_results["end_damage"])
        final_results["end_damage_rng_crit"] = final_results["end_damage_rng_crit"].where(~((final_results["source"] == "spell") & (final_results["can_spell_crit"] == 0)), final_results["end_damage"])
        
        final_results["total_damage_rng_crit"] = final_results["end_damage_rng_crit"].cumsum()
        final_results["total_damage_smooth_crit"] = final_results["end_damage_smooth_crit"].cumsum()
        
        final_results["seconds"] = final_results["time"] / 1000


        return(final_results)


g = GameManager()
g.add_champ(Champion(
        name='Soraka', 
        star_level = 2,        
        plot_label = "S2"
        # active_traits=["Scholar 2"],        
        # active_items=["Guinsoo's Rageblade"],
    )
)



target_df = pd.DataFrame({
            "target": ["main_tank", "frontline", "backline"], 
            "magic_resist": [70, 40, 20], 
            "armor": [70, 40, 20], 
            "durability": [.1, 0, 0]
        })
g.run_simulation(targets = target_df)
g.plot_results()
