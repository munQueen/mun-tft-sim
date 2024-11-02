import seaborn as sns
import matplotlib.pyplot as plt
import gameplay_sim 
import configparser

# Import data from shared.py

# get the list of choices
from shiny import App, render, ui, reactive

import pandas as pd 
items = pd.read_csv("C:\\Users\\Jess\\code\\tft_sim\\data\\csvs\\items.csv")
traits = pd.read_csv("C:\\Users\\Jess\\code\\tft_sim\\data\\csvs\\traits.csv")
spells = pd.read_csv("C:\\Users\\Jess\\code\\tft_sim\\data\\csvs\\spells.csv")


list_of_champs = spells["unit_name"].drop_duplicates().tolist()
list_of_items=pd.concat([pd.Series([""]), items["item_full_name"]], ignore_index=True).to_list()
list_of_traits = traits["trait"].drop_duplicates().to_list()

run_counter = 1


app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.accordion(
            ui.accordion_panel("Simulator", 
                ui.input_select("crit_smoothing", "Crit Smoothing [not functional]", ["Use Crit Smoothing", "Use RNG Crits"]),
                ui.input_text("duration", "Sim Duration (seconds) [not functional]", ""),            
            ),    
            ui.accordion_panel("Target Settings",                 
                ui.accordion(
                    ui.accordion_panel("Main Tank", 
                        ui.input_numeric("main_tank_armor", "Main Tank armor", value=80), 
                        ui.input_numeric("main_tank_magic_resist", "Main Tank MR", value=80),
                        ui.input_numeric("main_tank_durability", "Main Tank durability", value=10),
                    ),
                    ui.accordion_panel("Other Frontline", 
                        ui.input_numeric("frontline_armor", "Frontline armor", value=60), 
                        ui.input_numeric("frontline_magic_resist", "Frontline MR", value=60),
                        ui.input_numeric("frontline_durability", "Frontline durability", value=0),
                    ),     
                    ui.accordion_panel("Backline", 
                        ui.input_numeric("backline_armor", "Backline armor", value=60), 
                        ui.input_numeric("backline_magic_resist", "Backline MR", value=60),
                        ui.input_numeric("backline_durability", "Backline durability", value=0),
                    ),                                        
                ),          
            ),                    
            ui.accordion_panel("Champ 1",         
                ui.input_select("c1_champ", "Select champ", choices=list_of_champs),
                ui.input_select("c1_star_level", "Star level", choices=[1, 2, 3]),
                ui.input_select("c1_item_1", "Item 1", choices=list_of_items),
                ui.panel_conditional("input.c1_item_1 != ''", ui.input_select("c1_item_2", "Item 2", choices=list_of_items),),
                ui.panel_conditional("input.c1_item_2 != ''", ui.input_select("c1_item_3", "Item 3", choices=list_of_items),),
                ui.input_selectize(
                    id="c1_traits",
                    label="Traits [not functional]",
                    choices=list_of_traits,
                    multiple=True,
                ),
            ),
            ui.accordion_panel("Champ 2 Settings",         
                ui.input_select("c2_champ", "Select champ", choices=list_of_champs),
                ui.input_select("c2_star_level", "Star level", choices=[1, 2, 3]),
                ui.input_select("c2_item_1", "Item 1", choices=list_of_items),
                ui.panel_conditional("input.c2_item_1 != ''", ui.input_select("c2_item_2", "Item 2", choices=list_of_items),),
                ui.panel_conditional("input.c2_item_2 != ''", ui.input_select("c2_item_3", "Item 3", choices=list_of_items),),
                ui.input_text("c2_plot_label", "Run Label", ""),
                ui.input_selectize(
                    id="c2_traits",
                    label="Traits [not functional]",
                    choices=list_of_traits,
                    multiple=True,
                ),
            ),
        ),      
        ui.input_action_button("run_simulation", "Run"),
    ),
    ui.output_plot("plot"),
    title="Jess's Super Cool TFT Simulator",
)


def server(input, output, session):
    @render.plot
    @reactive.event(input.run_simulation)
    def plot():
        game = gameplay_sim.GameManager()
        game.add_champ(
            gameplay_sim.Champion(       
                name=str(input.c1_champ()), 
                star_level=int(input.c1_star_level()), 
                plot_label="Champ 1",
                active_items = [input.c1_item_1(), input.c1_item_2(), input.c1_item_3()]
            )
        )                
        game.run_simulation()
        sns.lineplot(x="seconds", y="total_damage", data=game.game_results, hue="plot_label")
        print(game.game_results)
        
            


app = App(app_ui, server)
