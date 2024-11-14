from pathlib import Path

import pandas as pd 
import random
import janitor
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
app_dir = Path(__file__).parent

spell = pd.read_csv(app_dir/"data/csvs/spells.csv")

spell_numeric_columns = spell.select_dtypes(include='number').columns

spell[spell_numeric_columns].fillna(0, inplace=True)
print(spell)
