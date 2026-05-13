import re

with open("analyzer.py", "r", encoding="utf-8") as f:
    content = f.read()

# Pattern to find: ax.bar in cross analysis followed by ax.set_xticks (no text labels between)
# The cross analysis has two bars (sum and mean), both missing labels

# Find the cross analysis section and add text labels after each bar
old_cross_sum = """                ax.bar(range(len(grouped_show)), grouped_show["sum"].values,
                       color=CHART_COLORS[:len(grouped_show)], edgecolor="white")
                ax.set_xticks(range(len(grouped_show)))
                ax.set_xticklabels([_shorten(x,6) for x in grouped_show.index], rotation=25, ha="right", fontsize=7)
                ax.set_title(f"{chr(21508)}{_shorten(cat_col)}{chr(30340)}{num_col}{chr(24635)}{chr(21644)}", fontweight="bold", fontsize=10)"""

new_cross_sum = """                bars_sum = ax.bar(range(len(grouped_show)), grouped_show["sum"].values,
                       color=CHART_COLORS[:len(grouped_show)], edgecolor="white")
                for bar, val in zip(bars_sum, grouped_show["sum"].values):
                    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
                            f"{val:,.0f}", ha="center", va="bottom", fontsize=7)
                ax.set_xticks(range(len(grouped_show)))
                ax.set_xticklabels([_shorten(x,6) for x in grouped_show.index], rotation=25, ha="right", fontsize=7)
                ax.set_title(f"{chr(21508)}{_shorten(cat_col)}{chr(30340)}{num_col}{chr(24635)}{chr(21644)}", fontweight="bold", fontsize=10)"""

if old_cross_sum in content:
    content = content.replace(old_cross_sum, new_cross_sum)
    print("Cross sum labels added.")
else:
    print("WARNING: cross sum pattern not found!")

# Add labels for the mean chart too
old_cross_mean = """                ax.bar(range(len(grouped_show)), grouped_show["mean"].values,
                       color=CHART_COLORS[:len(grouped_show)], edgecolor="white")
                ax.set_xticks(range(len(grouped_show)))
                ax.set_xticklabels([_shorten(x,6) for x in grouped_show.index], rotation=25, ha="right", fontsize=7)
                ax.set_title(f"{chr(21508)}{_shorten(cat_col)}{chr(30340)}{num_col}{chr(22343)}{chr(20540)}", fontweight="bold", fontsize=10)"""

new_cross_mean = """                bars_mean = ax.bar(range(len(grouped_show)), grouped_show["mean"].values,
                       color=CHART_COLORS[:len(grouped_show)], edgecolor="white")
                for bar, val in zip(bars_mean, grouped_show["mean"].values):
                    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
                            f"{val:,.1f}", ha="center", va="bottom", fontsize=7)
                ax.set_xticks(range(len(grouped_show)))
                ax.set_xticklabels([_shorten(x,6) for x in grouped_show.index], rotation=25, ha="right", fontsize=7)
                ax.set_title(f"{chr(21508)}{_shorten(cat_col)}{chr(30340)}{num_col}{chr(22343)}{chr(20540)}", fontweight="bold", fontsize=10)"""

if old_cross_mean in content:
    content = content.replace(old_cross_mean, new_cross_mean)
    print("Cross mean labels added.")
else:
    print("WARNING: cross mean pattern not found!")

with open("analyzer.py", "w", encoding="utf-8") as f:
    f.write(content)
print("analyzer.py updated.")
