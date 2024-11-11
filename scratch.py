from pathlib import Path

import pandas as pd 
import random
import janitor
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
app_dir = Path(__file__).parent

targets = pd.read_csv(app_dir/"data/csvs/targets_structure.csv")
targets = targets.drop(targets[(targets.category == "frontline") & (targets.unit_number > 2)].index)
# targets["armor"] = np.where(targets["category"]=="frontline", 10)
#targets.loc[targets["category"] == "frontline", 'armor'] = 10



defenses = pd.DataFrame({
            "category": ["main_tank", "frontline", "backline"], 
            "magic_resist": [70, 40, 20], 
            "armor": [70, 40, 20], 
            "durability": [.1, 0, 0]
        })


f = targets.merge(defenses, on='category')

print(f)

names = f.loc[(f.target == "main_tank") | (f.is_adjacent_to_main_tank == 1)][["target"]].values
print(names)
for name in names: 
    print(name.item())