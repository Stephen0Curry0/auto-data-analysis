"""
数据分析引擎 v4：智能表头检测 + 字段语义理解 + Times New Roman
"""
import os, re, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from matplotlib import font_manager

warnings.filterwarnings("ignore")

# ── 字体初始化：Times New Roman 优先，微软雅黑作中文回退 ──
def _init_fonts():
    # 注册 Times New Roman 字体族
    for tnr_path in ["C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf",
                     "C:/Windows/Fonts/timesbi.ttf", "C:/Windows/Fonts/timesi.ttf"]:
        if os.path.exists(tnr_path):
            font_manager.fontManager.addfont(tnr_path)
    # 注册中文字体（SimHei 黑体优先，宋体作备选）
    for zh_path in ["C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"]:
        if os.path.exists(zh_path):
            font_manager.fontManager.addfont(zh_path)
    # Times New Roman 优先，缺失字形自动回退到中文字体

    plt.rcParams["font.family"] = ["Times New Roman", "SimHei", "SimSun"]
    plt.rcParams["axes.unicode_minus"] = False
_init_fonts()

CHART_COLORS = ["#2b6cb0","#c53030","#2f855a","#dd6b20","#6b46c1","#3182ce","#e53e3e","#38a169","#ed8936","#805ad5"]

def set_style():
    sns.set_style("whitegrid")
    plt.rcParams["font.family"] = ["Times New Roman", "SimHei", "SimSun"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams.update({"figure.dpi":150,"savefig.dpi":150,"savefig.bbox":"tight",
        "font.size":13,"axes.titlesize":15,"axes.labelsize":11,
        "axes.spines.top":False,"axes.spines.right":False,"grid.alpha":0.3})

def _shorten(s, max_len=8):
    s = str(s).replace("\n"," ")
    return s if len(s) <= max_len else s[:max_len-1]+".."


# ═══════════════ 智能表头检测 ═══════════════

def detect_header_row(filepath):
    """
    自动检测 Excel 文件的真实表头行。
    返回 (header_row_index, raw_dataframe)
    """
    df_raw = pd.read_excel(filepath, header=None)
    best_row = 0
    best_score = -1

    for i in range(min(20, len(df_raw))):
        row = df_raw.iloc[i]
        non_null = row.notna().sum()
        if non_null < 2:
            continue
        # 评分：字符串(表头特征) +1, 纯数字(数据特征) -1
        score = 0
        for v in row.dropna():
            if isinstance(v, str):
                # 短字符串更像表头
                score += 2 if len(v) < 40 else 1
            elif isinstance(v, (int, float)):
                score -= 1
        # 行号靠后的表头不太合理，轻微惩罚
        score -= i * 0.3
        if score > best_score:
            best_score = score
            best_row = i

    return best_row, df_raw


# ═══════════════ 字段语义知识库 ═══════════════

# 字段名 -> (实体标签, 是否计数用"个")
ENTITY_KNOWLEDGE = {
    # 中文
    "客户": ("客户", "位"), "用户": ("用户", "位"), "会员": ("会员", "位"), "消费者": ("消费者", "位"),
    "商品": ("商品", "种"), "产品": ("产品", "种"), "货品": ("货品", "种"), "货物": ("货物", "种"),
    "员工": ("员工", "位"), "职员": ("职员", "位"), "人员": ("人员", "位"), "销售代表": ("销售代表", "位"),
    "城市": ("城市", "座"), "省份": ("省份", "个"), "国家": ("国家", "个"), "地区": ("地区", "个"),
    "部门": ("部门", "个"), "供应商": ("供应商", "家"), "店铺": ("店铺", "家"),
    "门店": ("门店", "家"), "品牌": ("品牌", "个"), "社区": ("社区", "个"), "街区": ("街区", "个"),
    "类别": ("类别", "种"), "类型": ("类型", "种"), "状态": ("状态", "种"), "渠道": ("渠道", "种"),
    "大洲": ("大洲", "个"), "语言": ("语言", "种"), "货币": ("货币", "种"),
    "职位": ("职位", "种"), "季节": ("季节", "个"), "支付方式": ("支付方式", "种"),
    "配送状态": ("配送状态", "种"), "客户等级": ("客户等级", "种"), "停车": ("停车", "种"),
    # 英文
    "country": ("国家", "个"), "capital": ("首都", "个"), "continent": ("大洲", "个"),
    "city": ("城市", "座"), "language": ("语言", "种"), "currency": ("货币", "种"),
    "government": ("政体", "种"),
    "region": ("地区", "个"), "neighborhood": ("社区", "个"), "department": ("部门", "个"),
    "position": ("职位", "种"), "season": ("季节", "个"), "category": ("类别", "种"),
    "channel": ("渠道", "种"), "tier": ("等级", "种"), "status": ("状态", "种"),
    "payment": ("支付方式", "种"), "delivery": ("配送状态", "种"),
    "type": ("类型", "种"), "parking": ("停车", "种"), "furnished": ("装修", "种"),
}


def understand_field(col_name):
    """理解字段含义，返回 (显示名, 量词, 是实体)"""
    clean = str(col_name).replace("\n", " ").strip()
    for key, (label, quantifier) in ENTITY_KNOWLEDGE.items():
        if key.lower() in clean.lower():
            return label, quantifier, True
    return clean, "个", False


# ═══════════════ 字段语义关系检测 ═══════════════

class FieldSemantics:
    def __init__(self, df):
        self.df = df
        self.num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        self.trivial_pairs = set()
        self.field_roles = {}
        self._analyze()

    def _analyze(self):
        for i, a in enumerate(self.num_cols):
            for j, b in enumerate(self.num_cols):
                if j <= i: continue
                for c in self.num_cols:
                    if c == a or c == b: continue
                    product = self.df[a] * self.df[b]
                    if product.std() == 0: continue
                    ratio = self.df[c] / product.replace(0, np.nan)
                    if ratio.notna().sum() > len(self.df) * 0.8:
                        if 0.95 < ratio.median() < 1.05:
                            for x, y in [(a,c),(b,c),(c,a),(c,b)]:
                                self.trivial_pairs.add((x,y))
                            self.field_roles[c] = "计算字段(≈"+a+"×"+b+")"
                            self.field_roles[a] = "基础指标"
                            self.field_roles[b] = "基础指标"


# ═══════════════ 数据清洗 ═══════════════

class DataCleaner:
    def __init__(self):
        self.log = []

    def _add_log(self, step, before, after, detail=""):
        self.log.append({"步骤":step,"清洗前":before,"清洗后":after,"详情":detail})

    def clean(self, df, filepath=None):
        df = df.copy()
        # 清理列名中的换行符和多余空格
        df.columns = [str(c).replace(chr(10)," ").replace(chr(13)," ").strip() for c in df.columns]
        # 删除明显的序号列（No./序号/编号等）
        skip_cols = []
        for c in df.columns:
            cl = str(c).lower().strip()
            if cl in ["no", "no.", "序号", "编号", "id"]:
                skip_cols.append(c)
        if skip_cols:
            df = df.drop(columns=skip_cols)
            self._add_log("跳过序号列", ", ".join(skip_cols), "已移除", "序号列不参与分析")
        df = df.copy()
        n0 = len(df)

        # 清理列名
        new_cols = []
        unnamed_count = 0
        for c in df.columns:
            cs = str(c).strip()
            if cs.lower().startswith("unnamed"):
                unnamed_count += 1
            new_cols.append(cs)
        df.columns = new_cols
        if unnamed_count > 0:
            self._add_log("检测未命名列", f"{unnamed_count}列", "保留",
                          "Excel表头可能有合并单元格或不在首行")

        df = df.dropna(how="all").dropna(axis=1, how="all")
        removed_rows = n0 - len(df)
        if removed_rows > 0:
            self._add_log("删除全空行", f"{n0}行", f"{len(df)}行", f"删除{removed_rows}行")

        dup_count = df.duplicated().sum()
        if dup_count > 0:
            df = df.drop_duplicates()
            self._add_log("删除重复行", f"{dup_count}条", "0条", f"删除{dup_count}条")

        for col in df.columns:
            missing = df[col].isna().sum()
            if missing == 0: continue
            ratio = missing / len(df)
            if ratio > 0.3:
                self._add_log(f"删除列「{col}」", f"缺失率{ratio:.1%}", "已删除", "缺失率>30%")
                df = df.drop(columns=[col])
            elif pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].median())
                self._add_log(f"填充「{col}」", f"缺失{missing}", "已填充", "中位数填充")
            else:
                fill_val = df[col].mode()[0] if not df[col].mode().empty else ""
                df[col] = df[col].fillna(fill_val)
                self._add_log(f"填充「{col}」", f"缺失{missing}", "已填充", "众数填充")

        return df


# ═══════════════ 智能标题 ═══════════════

def generate_smart_title(df, filename):
    cols = [str(c).lower() for c in df.columns]
    col_text = " ".join(cols)

    theme_patterns = [
        (["employee", "salary", "performance", "department", "position", "promotion"], "员工绩效"),
        (["price", "area", "bedroom", "bathroom", "sqft", "parking", "furnished"], "房地产"),
        (["temp", "rainfall", "humidity", "wind", "weather", "season", "uv"], "气象"),
        (["ecommerce", "delivery", "discount", "payment", "rating", "tier"], "电商"),
        (["sales", "revenue", "profit", "cost", "product", "channel", "customer"], "销售"),
        (["gdp", "population", "country", "continent", "world", "economy"], "经济"),
    ]

    best_theme, best_score = "", 0
    for keywords, label in theme_patterns:
        score = sum(1 for kw in keywords if kw in col_text)
        if score > best_score:
            best_score = score
            best_theme = label

    if best_score >= 2:
        return f"{best_theme}数据分析报告"

    fallback = ["销售","商品","客户","订单","库存","财务","员工",
                "房产","房地产","天气","气象","电商","绩效"]
    for t in fallback:
        if t in col_text:
            return f"{t}数据分析报告"

    base = os.path.splitext(filename)[0]
    import re
    base_clean = re.sub(r"^\d+[_\s-]+", "", base)
    base_clean = base_clean.replace("_", " ").replace("-", " ")
    return f"{base_clean} 数据分析报告"


def generate_smart_filename(df, filename):
    base = os.path.splitext(filename)[0]
    cols = [str(c).lower() for c in df.columns]
    col_text = " ".join(cols)

    tag_map = [
        (["ecommerce", "delivery", "rating", "tier"], "电商分析"),
        (["employee", "salary", "performance", "department"], "员工分析"),
        (["price", "area", "bedroom", "sqft", "parking"], "房产分析"),
        (["temp", "rainfall", "humidity", "weather"], "气象分析"),
        (["sales", "revenue", "profit", "customer"], "销售分析"),
        (["gdp", "population", "country", "economy"], "经济分析"),
    ]
    for keywords, tag in tag_map:
        if any(kw in col_text for kw in keywords):
            return f"{tag}报告_{base}.pdf"
    return f"数据分析报告_{base}.pdf"


class InsightGenerator:
    @staticmethod
    def overview_insight(ov, header_row_info=None):
        parts = []
        parts.append(f"本数据集共包含 {ov['行数']} 条记录，涵盖 {ov['列数']} 个字段。")
        if header_row_info:
            parts.append(f"（表头位于原始Excel第{header_row_info+1}行，已自动识别。）")
        missing_any = any(v > 0 for v in ov["缺失值"].values())
        if missing_any:
            bad = [k for k,v in ov["缺失值"].items() if v > 0]
            parts.append(f"其中 {', '.join(bad)} 存在缺失，已自动处理。")
        else:
            parts.append("数据完整性良好，所有字段均无缺失值。")
        return " ".join(parts)

    @staticmethod
    def numeric_insight(col, stats, outliers_info, df_col=None):
        parts = []
        mean_v = stats.get("mean", 0)
        median_v = stats.get("50%", 0)
        std_v = stats.get("std", 0)
        min_v = stats.get("min", 0)
        max_v = stats.get("max", 0)
        q25 = stats.get("25%", 0)
        q75 = stats.get("75%", 0)

        if std_v > 0 and mean_v > 0:
            cv = std_v / mean_v
            if cv > 1:
                parts.append(f"变异系数{cv:.1f}，数据波动较大，说明该指标在不同记录间差异显著。")
            elif cv < 0.3:
                parts.append(f"变异系数{cv:.1f}，数据较为集中，说明该指标在不同记录间差异不大。")
            else:
                parts.append(f"变异系数{cv:.1f}，波动幅度适中。")

        if median_v > mean_v * 1.1:
            parts.append(f"中位数({median_v:.1f})明显大于均值({mean_v:.1f})，呈左偏分布，少数低值拉低了整体水平，大多数记录实际表现更好。")
        elif mean_v > median_v * 1.1:
            parts.append(f"均值({mean_v:.1f})明显大于中位数({median_v:.1f})，呈右偏分布，少数高值拉升了整体水平，大多数记录集中在较低区间。")

        iqr = q75 - q25
        parts.append(f"范围 [{min_v:,.1f}, {max_v:,.1f}]，均值 {mean_v:,.1f}，中间50%集中在 [{q25:,.1f}, {q75:,.1f}]。")

        if col in outliers_info:
            n = outliers_info[col]["数量"]
            pct = n / (len(df_col) if df_col is not None else 100) * 100
            parts.append(f"检出 {n} 个离群值（占比约 {pct:.0f}%），建议核实是否为数据录入错误或特殊案例。")
        else:
            parts.append("未检出明显离群值，数据分布正常。")

        return " ".join(parts)

    @staticmethod
    def category_insight(col, vc, unique_n):
        label, quantifier, is_entity = understand_field(col)
        parts = []
        top1 = vc.index[0]
        top1_pct = vc.iloc[0] / vc.sum() * 100
        top3_sum = vc.iloc[:3].sum()
        top3_pct = top3_sum / vc.sum() * 100

        if is_entity:
            parts.append(f"共 {unique_n} {quantifier}{label}。"
                        f"「{top1}」以 {vc.iloc[0]} 次（{top1_pct:.0f}%）位居首位，是第二名的 {vc.iloc[0]/max(vc.iloc[1],1):.1f} 倍。")
        else:
            parts.append(f"共 {unique_n} 种{label}。"
                        f"「{top1}」出现 {vc.iloc[0]} 次（{top1_pct:.0f}%），占主导地位。")

        if top3_pct > 70:
            parts.append(f"前3类合计占比 {top3_pct:.0f}%，头部集中效应明显，资源配置可向头部倾斜。")
        elif top3_pct < 40:
            parts.append(f"前3类合计仅 {top3_pct:.0f}%，分布分散，无明显头部优势。")

        if len(vc) > 5:
            tail_count = vc.iloc[5:].sum()
            tail_pct = tail_count / vc.sum() * 100
            if tail_pct < 10:
                parts.append(f"第6名之后合计仅占 {tail_pct:.0f}%，长尾部分影响微弱。")
            else:
                parts.append(f"第6名之后合计占 {tail_pct:.0f}%，长尾效应值得关注。")

        return " ".join(parts)

    @staticmethod
    def correlation_insight(strong_pairs, semantics):
        meaningful = []
        for p in strong_pairs:
            a, b = p["列1"], p["列2"]
            if (a,b) in semantics.trivial_pairs or (b,a) in semantics.trivial_pairs:
                continue
            meaningful.append(p)

        if not meaningful:
            return "去除数学派生关系后，各字段间未发现强相关（|r|>0.5），表明字段独立性较好，无冗余信息。"

        parts = []
        for p in meaningful[:4]:
            direction = "正" if p["关系"] == "正相关" else "负"
            r_val = p['相关系数']
            strength = "强" if abs(r_val) > 0.8 else "中等偏强" if abs(r_val) > 0.65 else "中等"
            parts.append(
                f"「{p['列1']}」与「{p['列2']}」呈{strength}{direction}相关（r={r_val}），"
                f"意味着一个字段的变化会显著影响另一个字段，可重点关注其联动规律。"
            )
        return " ".join(parts)

    @staticmethod
    def time_insight(info):
        parts = []
        parts.append(f"时间跨度：{info.get('时间范围','')}。")
        parts.append("可结合业务节点进一步解读趋势变化。")
        return " ".join(parts)

    @staticmethod
    def cross_insight(cat_col, num_col, grouped):
        cat_label, quantifier, _ = understand_field(cat_col)
        parts = []
        top_cat = grouped.index[0]
        bottom_cat = grouped.index[-1]
        top_val = grouped.iloc[0]["sum"]
        bottom_val = grouped.iloc[-1]["sum"]
        diff = top_val / max(bottom_val, 0.01)
        parts.append(f"按{cat_label}维度，「{top_cat}」的{num_col}总计最高")
        if diff > 3:
            parts.append(f"，是末位「{bottom_cat}」的 {diff:.1f} 倍，差距显著。")
        else:
            parts.append("，各{cat_label}之间差异相对均衡。")
        return " ".join(parts)


# ═══════════════ 数据分析器 ═══════════════

class DataAnalyzer:
    def __init__(self, output_dir="outputs"):
        self.output_dir = output_dir
        self.chart_dir = os.path.join(output_dir, "charts")
        os.makedirs(self.chart_dir, exist_ok=True)
        self.charts = []
        self.insights = InsightGenerator()
        set_style()

    def analyze(self, df, filename, header_row=None):
        self.charts = []
        self.semantics = FieldSemantics(df)

        results = {
            "filename": filename,
            "smart_title": generate_smart_title(df, filename),
            "smart_filename": generate_smart_filename(df, filename),
            "header_row": header_row,
            "overview": self._overview(df, header_row),
            "numeric_analysis": self._numeric_analysis(df),
            "category_analysis": self._category_analysis(df),
            "time_analysis": self._time_analysis(df),
            "correlation": self._correlation(df),
            "cross_analysis": self._cross_analysis(df),
            "sales_analysis": self._sales_deep_analysis(df),
            "smart_rankings": self._smart_rankings(df),
            "key_findings": [],
            "field_roles": self.semantics.field_roles,
        }
        results["binary_outcome"] = self._binary_outcome_analysis(df)
        results["key_findings"] = self._summarize_findings(df, results)
        return results

    def _overview(self, df, header_row=None):
        info = {"行数":len(df),"列数":len(df.columns),"列名":list(df.columns),
                "缺失值":{c:int(df[c].isna().sum()) for c in df.columns},
                "重复行":int(df.duplicated().sum())}

        type_counts = {}
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]): t = "数值型"
            elif pd.api.types.is_datetime64_any_dtype(df[c]): t = "日期型"
            else: t = "文本型"
            type_counts[t] = type_counts.get(t, 0) + 1

        fig, ax = plt.subplots(figsize=(3,3))
        cmap = {"数值型":"#2b6cb0","文本型":"#c53030","日期型":"#2f855a"}
        ax.pie(type_counts.values(), labels=type_counts.keys(),
               colors=[cmap.get(k,"#ccc") for k in type_counts],
               autopct="%1.1f%%", startangle=90, pctdistance=0.65)
        ax.set_title("字段类型分布", fontweight="bold", fontsize=14.0)
        self._save_chart(fig, "overview_types.png")

        info["insight"] = self.insights.overview_insight(info, header_row)
        return info

    def _numeric_analysis(self, df):
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not num_cols:
            return {"存在":False}

        result = {"存在":True, "列":num_cols, "统计":{}, "洞察":{}, "图表":{}}
        result["统计"] = df[num_cols].describe().round(2).to_dict()

        outliers_info = {}
        for col in num_cols:
            Q1, Q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            IQR = Q3 - Q1
            cnt = ((df[col] < Q1-1.5*IQR) | (df[col] > Q3+1.5*IQR)).sum()
            if cnt > 0:
                outliers_info[col] = {"数量":int(cnt)}

        result["异常值"] = outliers_info

        cols_to_plot = num_cols[:6]
        for i, col in enumerate(cols_to_plot):
            data = df[col].dropna()
            fig, ax = plt.subplots(figsize=(4.5, 3))
            ax.hist(data, bins=min(18, len(data)), color=CHART_COLORS[i%len(CHART_COLORS)],
                    edgecolor="white", alpha=0.85)
            ax.axvline(data.mean(), color="#c53030", linestyle="--", linewidth=1.5,
                      label=f"均值{data.mean():,.1f}")
            ax.axvline(data.median(), color="#2f855a", linestyle="-", linewidth=1,
                      label=f"中位数{data.median():,.1f}")
            ax.set_title(f"{_shorten(col,10)} 分布", fontweight="bold")
            ax.legend(fontsize=9.5, loc="upper right")
            ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            plt.tight_layout()
            result["图表"][col] = self._save_chart(fig, f"hist_{i}.png")
            if col in result["统计"]:
                result["洞察"][col] = self.insights.numeric_insight(
                    col, result["统计"][col], outliers_info)

        if len(cols_to_plot) > 1:
            fig, ax = plt.subplots(figsize=(max(7, len(cols_to_plot)*1.4), 3.5))
            bp_data = [df[c].dropna().values for c in cols_to_plot]
            short_names = [_shorten(c, 8) for c in cols_to_plot]
            bp = ax.boxplot(bp_data, labels=short_names, patch_artist=True, widths=0.5,
                            showmeans=True, meanprops=dict(marker="D", markerfacecolor="#c53030", markersize=5))
            for patch, color in zip(bp["boxes"], CHART_COLORS[:len(cols_to_plot)]):
                patch.set_facecolor(color); patch.set_alpha(0.6)
            ax.set_title("数值字段箱线图对比", fontweight="bold")
            plt.tight_layout()
            result["图表"]["箱线图"] = self._save_chart(fig, "numeric_boxplot.png")

        return result

    def _category_analysis(self, df):
        cat_cols = df.select_dtypes(include=["object","category"]).columns.tolist()
        # Skip fields where most values are unique (e.g., IDs, names)
        cat_cols = [c for c in cat_cols if df[c].nunique() < max(20, len(df) * 0.5)]
        if not cat_cols:
            return {"存在":False}

        result = {"存在":True, "列":cat_cols, "详情":{}}
        for col in cat_cols:
            vc = df[col].value_counts()
            if len(vc) > 12:
                vc_plot = vc.head(10)
                note = f"(共{len(vc)}类，展前10)"
            else:
                vc_plot = vc
                note = ""

            labels = [_shorten(str(x), 10) for x in vc_plot.index]
            fig, ax = plt.subplots(figsize=(max(5, len(vc_plot)*0.55), 3.2))
            colors = [CHART_COLORS[i%len(CHART_COLORS)] for i in range(len(vc_plot))]
            bars = ax.bar(range(len(vc_plot)), vc_plot.values, color=colors, edgecolor="white", linewidth=0.5)
            ax.set_xticks(range(len(vc_plot)))
            ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9.5)
            ax.set_ylabel("频次")
            ax.set_title(f"{_shorten(col,10)} 频次分布 {note}", fontweight="bold", fontsize=14.0)
            ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            for bar, val in zip(bars, vc_plot.values):
                ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3,
                        str(val), ha="center", va="bottom", fontsize=10.5, fontweight="bold")
            plt.tight_layout()
            safe_col = re.sub(r"[\\/:*?\"<>|]","_", col)
            result["详情"][col] = {
                "频次": vc.head(12).to_dict(),
                "唯一值数": int(df[col].nunique()),
                "图表": self._save_chart(fig, f"cat_{safe_col}.png"),
                "洞察": self.insights.category_insight(col, vc, int(df[col].nunique())),
            }
        return result

    def _time_analysis(self, df):
        time_cols = df.select_dtypes(include=["datetime"]).columns.tolist()
        if not time_cols:
            return {"存在":False}

        result = {"存在":True, "列":time_cols, "详情":{}}
        for col in time_cols:
            info = {"时间范围":f"{df[col].min()} ~ {df[col].max()}",
                    "时间跨度":str(df[col].max()-df[col].min())}
            info["洞察"] = self.insights.time_insight(info)
            num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if num_cols:
                first_num = num_cols[0]
                daily = df.sort_values(col).set_index(col).resample("D")[first_num].sum().reset_index()
                if len(daily) >= 2:
                    fig, ax = plt.subplots(figsize=(6.5, 3))
                    ax.plot(daily[col], daily[first_num], marker="o", color="#2b6cb0",
                            linewidth=2, markersize=5, markerfacecolor="white", markeredgewidth=1.5)
                    ax.fill_between(daily[col], daily[first_num], alpha=0.12, color="#2b6cb0")
                    ax.set_title(f"「{first_num}」每日趋势", fontweight="bold")
                    ax.set_xlabel("日期"); ax.set_ylabel(_shorten(first_num,10))
                    fig.autofmt_xdate()
                    plt.tight_layout()
                    info["趋势图"] = self._save_chart(fig, "time_trend.png")
            result["详情"][col] = info
        return result

    def _correlation(self, df):
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(num_cols) < 2:
            return {"存在":False}

        corr = df[num_cols].corr()
        result = {"存在":True, "矩阵":corr.round(3).to_dict()}

        short_names = [_shorten(c, 6) for c in num_cols]
        corr_short = corr.copy()
        corr_short.index = short_names
        corr_short.columns = short_names

        fig, ax = plt.subplots(figsize=(max(4.5, len(num_cols)), max(3.5, len(num_cols)*0.85)))
        mask = np.triu(np.ones_like(corr_short, dtype=bool), k=1)
        sns.heatmap(corr_short, mask=mask, annot=True, fmt=".2f", cmap="RdBu_r",
                    center=0, vmin=-1, vmax=1, square=True, linewidths=0.8,
                    cbar_kws={"shrink":0.75}, ax=ax, annot_kws={"fontsize":10})
        ax.set_title("数值字段相关系数热力图", fontweight="bold", fontsize=15.0)
        plt.tight_layout()
        result["热力图"] = self._save_chart(fig, "corr_heatmap.png")

        strong_pairs = []
        for i in range(len(num_cols)):
            for j in range(i+1, len(num_cols)):
                v = corr.iloc[i, j]
                if abs(v) > 0.5:
                    a, b = num_cols[i], num_cols[j]
                    if (a,b) in self.semantics.trivial_pairs or (b,a) in self.semantics.trivial_pairs:
                        continue
                    strong_pairs.append({"列1":a,"列2":b,"相关系数":round(v,3),
                                         "关系":"正相关" if v>0 else "负相关"})
        result["强相关"] = strong_pairs
        result["洞察"] = self.insights.correlation_insight(strong_pairs, self.semantics)
        return result

    def _cross_analysis(self, df):
        cat_cols = df.select_dtypes(include=["object","category"]).columns.tolist()
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not cat_cols or not num_cols:
            return {"存在":False}

        results = {"存在":True, "分析":[]}
        for cat_col in cat_cols[:2]:
            if df[cat_col].nunique() > 15:
                continue
            for num_col in num_cols[:2]:
                grouped = df.groupby(cat_col)[num_col].agg(["sum","mean"]).sort_values("sum", ascending=False)
                show_n = min(12, len(grouped))
                grouped_show = grouped.head(show_n)

                fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
                ax = axes[0]
                bars_sum = ax.bar(range(len(grouped_show)), grouped_show["sum"].values,
                       color=CHART_COLORS[:len(grouped_show)], edgecolor="white")
                for bar, val in zip(bars_sum, grouped_show["sum"].values):
                    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.4,
                            f"{val:,.0f}", ha="center", va="bottom", fontsize=10.5, fontweight="bold")
                ax.set_xticks(range(len(grouped_show)))
                ax.set_xticklabels([_shorten(x,6) for x in grouped_show.index], rotation=25, ha="right", fontsize=9.5)
                ax.set_title(f"各{_shorten(cat_col)}的{num_col}总和", fontweight="bold", fontsize=15.0)

                ax = axes[1]
                bars_mean = ax.bar(range(len(grouped_show)), grouped_show["mean"].values,
                       color=CHART_COLORS[:len(grouped_show)], edgecolor="white")
                for bar, val in zip(bars_mean, grouped_show["mean"].values):
                    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.4,
                            f"{val:,.1f}", ha="center", va="bottom", fontsize=10.5, fontweight="bold")
                ax.set_xticks(range(len(grouped_show)))
                ax.set_xticklabels([_shorten(x,6) for x in grouped_show.index], rotation=25, ha="right", fontsize=9.5)
                ax.set_title(f"各{_shorten(cat_col)}的{num_col}均值", fontweight="bold", fontsize=15.0)
                ax.axhline(df[num_col].mean(), color="#c53030", linestyle="--", linewidth=1,
                           label=f"整体均值{df[num_col].mean():,.1f}")
                ax.legend(fontsize=9.5)

                fig.suptitle(f"{_shorten(cat_col)} x {num_col} 交叉分析", fontsize=15, fontweight="bold")
                plt.tight_layout()
                chart = self._save_chart(fig, f"cross_{cat_col}_{num_col}.png")
                results["分析"].append({
                    "分类":cat_col,"数值":num_col,"图表":chart,
                    "洞察":self.insights.cross_insight(cat_col, num_col, grouped),
                })
                break
        return results

    def _sales_deep_analysis(self, df):
        """????????????????????????????"""
        # ??????????
        cols_lower = {c.lower(): c for c in df.columns}
        has_time = any(k in cols_lower for k in ["时间", "日期", "date", "time"])
        has_customer = any(k in cols_lower for k in ["客户", "用户", "customer", "client", "会员"])
        has_product = any(k in cols_lower for k in ["商品", "产品", "product", "item", "goods", "货品"])
        has_amount = any(k in cols_lower for k in ["总价", "金额", "amount", "total", "revenue", "sales", "销售额", "营业额"])
        has_qty = any(k in cols_lower for k in ["数量", "quantity", "qty", "销量", "销售数量"])

        if not (has_time and (has_customer or has_product) and (has_amount or has_qty)):
            return {"存在": False}

        # ??????
        time_col = next((cols_lower[k] for k in ["时间", "日期", "date", "time"] if k in cols_lower), None)
        cust_col = next((cols_lower[k] for k in ["客户", "用户", "customer", "client", "会员"] if k in cols_lower), None)
        prod_col = next((cols_lower[k] for k in ["商品", "产品", "product", "item", "goods", "货品"] if k in cols_lower), None)
        amt_col = next((cols_lower[k] for k in ["总价", "金额", "amount", "total", "revenue", "sales", "销售额", "营业额"] if k in cols_lower), None)
        qty_col = next((cols_lower[k] for k in ["数量", "quantity", "qty", "销量", "销售数量"] if k in cols_lower), None)

        result = {"存在": True}

        # ?????? datetime ??
        if time_col and not pd.api.types.is_datetime64_any_dtype(df[time_col]):
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

        # ?? ?????? ??
        if amt_col and df[amt_col].dtype in [np.float64, np.int64, np.float32, np.int32]:
            result["总销售额"] = float(df[amt_col].sum())
        else:
            result["总销售额"] = 0.0
        if qty_col and df[qty_col].dtype in [np.float64, np.int64, np.float32, np.int32]:
            result["总销量"] = int(df[qty_col].sum())
        else:
            result["总销量"] = 0
        result["客户数"] = int(df[cust_col].nunique()) if cust_col else 0
        result["商品数"] = int(df[prod_col].nunique()) if prod_col else 0
        result["客单价均值"] = float(df[amt_col].mean()) if amt_col and len(df) > 0 else 0.0
        result["记录数"] = len(df)

        # ?? ?????? ??
        daily_chart = None
        best_day_info = None
        worst_day_info = None
        if time_col and amt_col:
            df_sorted = df.sort_values(time_col).copy()
            df_sorted["日期"] = df_sorted[time_col].dt.date
            daily = df_sorted.groupby("日期")[amt_col].sum().reset_index()
            daily.columns = ["日期", "销售额"]

            if len(daily) >= 2:
                import matplotlib.dates as mdates
                fig, ax = plt.subplots(figsize=(8, 3.5))
                dates = [pd.Timestamp(d) for d in daily["日期"]]
                ax.plot(dates, daily["销售额"].values, marker="o",
                        color="#2b6cb0", linewidth=2.5, markersize=7,
                        markerfacecolor="white", markeredgewidth=2)
                ax.fill_between(dates, daily["销售额"].values, alpha=0.15, color="#2b6cb0")
                # ?????????
                max_idx = daily["销售额"].idxmax()
                min_idx = daily["销售额"].idxmin()
                ax.annotate(f'{daily.iloc[max_idx]["销售额"]:,.0f}',
                            xy=(dates[max_idx], daily.iloc[max_idx]["销售额"]),
                            xytext=(0, 12), textcoords="offset points",
                            ha="center", fontsize=10.5, fontweight="bold", color="#c53030")
                ax.annotate(f'{daily.iloc[min_idx]["销售额"]:,.0f}',
                            xy=(dates[min_idx], daily.iloc[min_idx]["销售额"]),
                            xytext=(0, -16), textcoords="offset points",
                            ha="center", fontsize=10.5, color="#718096")
                ax.set_title(f"Daily Sales Trend", fontweight="bold", fontsize=16.0, color="#1a365d")
                ax.set_ylabel(amt_col if amt_col else "Amount")
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
                fig.autofmt_xdate()
                plt.tight_layout()
                daily_chart = self._save_chart(fig, "sales_daily_trend.png")

                # ???????
                best_row = daily.iloc[max_idx]
                best_date_str = str(best_row["日期"])
                # ????????????
                day_mask = df_sorted["日期"] == best_row["日期"]
                day_data = df_sorted[day_mask]
                best_day_info = {
                    "日期": best_date_str,
                    "销售额": float(best_row["销售额"]),
                }
                if prod_col and amt_col:
                    top_prod_day = day_data.groupby(prod_col)[amt_col].sum().sort_values(ascending=False)
                    if len(top_prod_day) > 0:
                        best_day_info["top商品"] = str(top_prod_day.index[0])
                if cust_col and amt_col:
                    top_cust_day = day_data.groupby(cust_col)[amt_col].sum().sort_values(ascending=False)
                    if len(top_cust_day) > 0:
                        best_day_info["top客户"] = str(top_cust_day.index[0])

                # ?????
                worst_row = daily.iloc[min_idx]
                worst_day_info = {
                    "日期": str(worst_row["日期"]),
                    "销售额": float(worst_row["销售额"]),
                }

        result["每日趋势图"] = daily_chart
        result["最佳销售日"] = best_day_info
        result["最差销售日"] = worst_day_info

        # ?? ?????? ??
        product_chart = None
        if prod_col and amt_col:
            prod_sales = df.groupby(prod_col)[amt_col].sum().sort_values(ascending=False)
            top_n = min(10, len(prod_sales))
            prod_top = prod_sales.head(top_n)
            result["top商品名称"] = str(prod_top.index[0])
            result["top商品销售额"] = float(prod_top.iloc[0])
            result["top商品占比"] = float(prod_top.iloc[0] / prod_sales.sum() * 100)
            result["商品排名"] = {str(k): float(v) for k, v in prod_top.items()}

            fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
            # ?????
            ax = axes[0]
            bars = ax.barh(range(len(prod_top)), prod_top.values[::-1],
                           color=[CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(prod_top)-1, -1, -1)],
                           edgecolor="white", height=0.7)
            ax.set_yticks(range(len(prod_top)))
            ax.set_yticklabels([_shorten(str(x), 8) for x in prod_top.index[::-1]], fontsize=9.5)
            ax.set_title(f"Top {top_n} Products by Revenue", fontweight="bold", fontsize=13)
            ax.set_xlabel("Revenue")
            for bar, val in zip(bars, prod_top.values[::-1]):
                ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                        f"{val:,.0f}", va="center", fontsize=10.5, fontweight="bold")
            # ???? (??????)
            ax = axes[1]
            if qty_col:
                prod_qty = df.groupby(prod_col)[qty_col].sum().sort_values(ascending=False)
                prod_qty_top = prod_qty.head(top_n)
                result["商品销量排名"] = {str(k): int(v) for k, v in prod_qty_top.items()}
                bars2 = ax.barh(range(len(prod_qty_top)), prod_qty_top.values[::-1],
                                color=[CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(prod_qty_top)-1, -1, -1)],
                                edgecolor="white", height=0.7)
                ax.set_yticks(range(len(prod_qty_top)))
                ax.set_yticklabels([_shorten(str(x), 8) for x in prod_qty_top.index[::-1]], fontsize=9.5)
                ax.set_title(f"Top {top_n} Products by Quantity", fontweight="bold", fontsize=13)
                ax.set_xlabel("Quantity")
                for bar, val in zip(bars2, prod_qty_top.values[::-1]):
                    ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                            f"{int(val)}", va="center", fontsize=10.5, fontweight="bold")
            fig.suptitle("Product Sales Ranking", fontsize=15, fontweight="bold", color="#1a365d")
            plt.tight_layout()
            product_chart = self._save_chart(fig, "sales_product_ranking.png")
        result["商品排名图"] = product_chart

        # ?? ?????? ??
        customer_chart = None
        if cust_col and amt_col:
            cust_sales = df.groupby(cust_col)[amt_col].sum().sort_values(ascending=False)
            top_n = min(10, len(cust_sales))
            cust_top = cust_sales.head(top_n)
            result["top客户名称"] = str(cust_top.index[0])
            result["top客户消费"] = float(cust_top.iloc[0])
            result["top客户占比"] = float(cust_top.iloc[0] / cust_sales.sum() * 100)
            result["客户排名"] = {str(k): float(v) for k, v in cust_top.items()}

            fig, ax = plt.subplots(figsize=(7, 3.5))
            bars = ax.barh(range(len(cust_top)), cust_top.values[::-1],
                           color=[CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(cust_top)-1, -1, -1)],
                           edgecolor="white", height=0.7)
            ax.set_yticks(range(len(cust_top)))
            ax.set_yticklabels([_shorten(str(x), 10) for x in cust_top.index[::-1]], fontsize=9.5)
            ax.set_title(f"Top {top_n} Customers by Spend", fontweight="bold", fontsize=13, color="#1a365d")
            ax.set_xlabel("Total Spend")
            for bar, val in zip(bars, cust_top.values[::-1]):
                ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                        f"{val:,.0f}", va="center", fontsize=10.5, fontweight="bold")
            plt.tight_layout()
            customer_chart = self._save_chart(fig, "sales_customer_ranking.png")
        result["客户排名图"] = customer_chart

        return result

    def _smart_rankings(self, df):
        """Universal smart ranking: auto-detect dimensions x measures, rank top-N."""
        dim_cols = []
        meas_cols = []
        for col in df.columns:
            if df[col].dtype in ["int64", "float64"]:
                meas_cols.append(col)
            elif df[col].dtype in ["object", "string"]:
                nunique = df[col].nunique()
                if 2 <= nunique <= max(50, len(df) * 0.7):
                    dim_cols.append(col)

        if not dim_cols or not meas_cols:
            return {"exists": False}

        rankings = []
        for dim in dim_cols[:6]:
            for meas in meas_cols[:6]:
                if dim == meas:
                    continue
                grouped = df.groupby(dim)[meas].sum().sort_values(ascending=False)
                if len(grouped) < 2:
                    continue
                top_n = min(10, len(grouped))
                top = grouped.head(top_n)
                total = grouped.sum()
                if total == 0:
                    continue
                top3_pct = top.head(3).sum() / total * 100 if total > 0 else 0
                top1_val = float(top.iloc[0])
                last_val = max(float(top.iloc[-1]), 0.001)
                max_min_ratio = top1_val / last_val
                score = top3_pct * 0.5 + min(max_min_ratio, 20) * 2.5
                rankings.append({
                    "dim": dim, "meas": meas,
                    "rank": [(str(k), float(v)) for k, v in top.items()],
                    "score": round(score, 1), "top3_pct": round(top3_pct, 1),
                    "top1_name": str(top.index[0]), "top1_val": top1_val,
                })

        rankings.sort(key=lambda x: x["score"], reverse=True)
        top_rankings = rankings[:6]

        result = {"exists": True, "items": []}
        for r in top_rankings:
            dim, meas = r["dim"], r["meas"]
            items = r["rank"][:10]
            fig, ax = plt.subplots(figsize=(7, max(2.5, len(items) * 0.4)))
            names = [_shorten(str(x), 12) for x, _ in reversed(items)]
            values = [v for _, v in reversed(items)]
            colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(items))]
            bars = ax.barh(range(len(items)), values, color=colors, edgecolor="white", height=0.7)
            ax.set_yticks(range(len(items)))
            ax.set_yticklabels(names, fontsize=9.5)
            ax.set_xlabel(meas, fontsize=13)
            ax.set_title(f"Top {len(items)} {dim} by {meas}", fontweight="bold", fontsize=14.0, color="#1a365d")
            for bar, val in zip(bars, values):
                ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                        f"{val:,.1f}" if val < 1000 else f"{val:,.0f}",
                        va="center", fontsize=10.5, fontweight="bold")
            plt.tight_layout()
            safe = re.sub(r"[\\/:*?<>|]", "_", f"{dim}_{meas}")
            chart_path = self._save_chart(fig, f"rank_{safe}.png")
            dim_label, quantifier, _ = understand_field(dim)
            tn = r["top1_name"]; tv = r["top1_val"]
            insight = f"{dim_label} TOP1: {tn} = {tv:,.1f}"
            if r["top3_pct"] > 60:
                tp = r["top3_pct"]
            if tp > 60:
                insight += f", top3 share {tp:.0f}%"
            result["items"].append({
                "dim": dim, "meas": meas, "chart": chart_path,
                "insight": insight, "rank_data": dict(items), "score": r["score"],
            })

        return result


        return results


    def _binary_outcome_analysis(self, df):
        """Analyze binary outcome fields (e.g., Promotion Eligible, Delivery Status)"""
        # Detect binary categorical columns (2 unique non-numeric values)
        binary_cols = []
        for col in df.columns:
            if df[col].dtype in ['object', 'string', 'str', 'category', 'O']:
                if df[col].nunique() == 2:
                    binary_cols.append(col)
        
        if not binary_cols:
            return {"exists": False}
        
        num_cols = df.select_dtypes(include=['number']).columns.tolist()
        cat_cols = [c for c in df.columns if df[c].dtype in ['object', 'string', 'str', 'category', 'O']
                    and c not in binary_cols and 2 <= df[c].nunique() <= 15]
        
        results = {"exists": True, "columns": binary_cols, "analyses": []}
        
        for bin_col in binary_cols[:2]:
            vals = list(df[bin_col].dropna().unique())
            if len(vals) < 2:
                continue
            # Smart detection: which value is the "positive" outcome?
            positive_keywords = ['yes', 'pass', 'true', 'eligible', 'promoted', '是', '通过', '合格', '晋升',
                                'high', 'good', 'delivered', 'completed', 'success', 'active']
            pos_val, neg_val = vals[0], vals[1]
            for v in vals:
                if any(kw in str(v).lower() for kw in positive_keywords):
                    pos_val = v
                    neg_val = [x for x in vals if x != v][0]
                    break
            pos_count = (df[bin_col] == pos_val).sum()
            neg_count = (df[bin_col] == neg_val).sum()
            total = pos_count + neg_count
            pass_rate = pos_count / total * 100 if total > 0 else 0
            # If positive outcome is negative-sounding (No/False), swap interpretation
            negative_keywords = ['no', 'false', 'fail', 'not', '否', '未', '不合格']
            if any(kw in str(pos_val).lower() for kw in negative_keywords):
                pos_val, neg_val = neg_val, pos_val
                pos_count, neg_count = neg_count, pos_count
                pass_rate = pos_count / total * 100 if total > 0 else 0
            
            analysis = {
                "column": bin_col,
                "positive_label": str(pos_val),
                "negative_label": str(neg_val),
                "positive_count": int(pos_count),
                "negative_count": int(neg_count),
                "pass_rate": round(pass_rate, 1),
                "comparisons": [],
                "category_breakdowns": [],
            }
            
            # Compare numeric fields between two groups
            group_pos = df[df[bin_col] == pos_val]
            group_neg = df[df[bin_col] == neg_val]
            
            diffs = []
            for nc in num_cols[:8]:
                p_mean = group_pos[nc].mean()
                n_mean = group_neg[nc].mean()
                if abs(p_mean) < 0.001 and abs(n_mean) < 0.001:
                    continue
                diff_pct = (p_mean - n_mean) / max(abs(n_mean), 0.001) * 100
                if abs(diff_pct) > 5:  # Only meaningful differences
                    diffs.append({
                        "column": nc,
                        "positive_mean": round(p_mean, 2),
                        "negative_mean": round(n_mean, 2),
                        "diff_pct": round(diff_pct, 1),
                    })
            
            # Sort by absolute difference, take top 6
            diffs.sort(key=lambda x: abs(x["diff_pct"]), reverse=True)
            top_diffs = diffs[:6]
            
            if top_diffs:
                # Create grouped bar chart for top diffs
                fig, ax = plt.subplots(figsize=(max(5, len(top_diffs) * 1.2), 3.5))
                x = range(len(top_diffs))
                w = 0.35
                labels_short = [_shorten(d["column"], 8) for d in top_diffs]
                bars1 = ax.bar([i - w/2 for i in x], [d["positive_mean"] for d in top_diffs],
                               w, label=str(pos_val), color="#2b6cb0", edgecolor="white")
                bars2 = ax.bar([i + w/2 for i in x], [d["negative_mean"] for d in top_diffs],
                               w, label=str(neg_val), color="#c53030", edgecolor="white")
                for bar, val in zip(bars1, [d["positive_mean"] for d in top_diffs]):
                    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.2,
                            f"{val:,.1f}", ha="center", va="bottom", fontsize=10.5, fontweight="bold")
                for bar, val in zip(bars2, [d["negative_mean"] for d in top_diffs]):
                    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.2,
                            f"{val:,.1f}", ha="center", va="bottom", fontsize=10.5, fontweight="bold")
                ax.set_xticks(list(x))
                ax.set_xticklabels(labels_short, rotation=15, ha="right", fontsize=9.5)
                ax.set_title(f"{bin_col}: {pos_val} vs {neg_val} Mean Comparison",
                            fontweight="bold", fontsize=13, color="#1a365d")
                ax.legend(fontsize=9.5)
                plt.tight_layout()
                safe = re.sub(r"[\\/:*?<>|]", "_", bin_col)
                chart_path = self._save_chart(fig, f"binary_{safe}_compare.png")
                
                # Build insight
                insight_parts = [f"通过率 {pass_rate:.0f}%（{pos_count}/{total}）。"]
                top3 = top_diffs[:3]
                for d in top3:
                    direction = "高于" if d["diff_pct"] > 0 else "低于"
                    insight_parts.append(
                        f"「{d['column']}」{pos_val}组均值{d['positive_mean']:,.1f}，"
                        f"{direction}{neg_val}组{d['negative_mean']:,.1f}（{abs(d['diff_pct']):.0f}%）。"
                    )
                
                analysis["comparisons"] = top_diffs
                analysis["comparison_chart"] = chart_path
                analysis["insight"] = " ".join(insight_parts)
            
            # Category breakdown: pass rate per category
            cat_breakdowns = []
            for cc in cat_cols[:4]:
                if cc == bin_col:
                    continue
                grouped = df.groupby(cc)[bin_col].apply(
                    lambda x: (x == pos_val).sum() / len(x) * 100 if len(x) >= 3 else None
                ).dropna().sort_values(ascending=False)
                if len(grouped) >= 2:
                    top_cat = grouped.index[0]
                    bot_cat = grouped.index[-1]
                    spread = grouped.iloc[0] - grouped.iloc[-1]
                    if spread > 15:  # Only show if meaningful spread
                        cat_breakdowns.append({
                            "category_field": cc,
                            "data": {str(k): round(float(v), 1) for k, v in grouped.items()},
                            "top": (str(top_cat), round(float(grouped.iloc[0]), 1)),
                            "bottom": (str(bot_cat), round(float(grouped.iloc[-1]), 1)),
                            "spread": round(float(spread), 1),
                        })
            
            if cat_breakdowns:
                cat_breakdowns.sort(key=lambda x: x["spread"], reverse=True)
                top_cats = cat_breakdowns[:3]
                for cb in top_cats:
                    data = cb["data"]
                    items = sorted(data.items(), key=lambda x: x[1], reverse=True)
                    fig, ax = plt.subplots(figsize=(max(5, len(items) * 0.6), 3.2))
                    names = [_shorten(str(k), 10) for k, v in items]
                    values = [v for k, v in items]
                    colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(items))]
                    bars = ax.bar(range(len(items)), values, color=colors, edgecolor="white")
                    for bar, val in zip(bars, values):
                        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                                f"{val:.0f}%", ha="center", va="bottom", fontsize=10.5, fontweight="bold")
                    ax.set_xticks(range(len(items)))
                    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=9.5)
                    ax.set_ylabel("Pass Rate (%)")
                    ax.set_title(f"{bin_col} Pass Rate by {cb['category_field']}",
                                fontweight="bold", fontsize=14.0)
                    ax.set_ylim(0, min(110, max(values) * 1.3))
                    plt.tight_layout()
                    safe_b = re.sub(r"[\\/:*?<>|]", "_", bin_col)
                    safe_c = re.sub(r"[\\/:*?<>|]", "_", cb["category_field"])
                    cb["chart"] = self._save_chart(fig, f"binary_{safe_b}_by_{safe_c}.png")
                
                analysis["category_breakdowns"] = top_cats
                if top_cats:
                    cb = top_cats[0]
                    analysis["cat_insight"] = (
                        f"按{cb['category_field']}分析，{cb['top'][0]}通过率最高（{cb['top'][1]:.0f}%），"
                        f"{cb['bottom'][0]}最低（{cb['bottom'][1]:.0f}%），差距{cb['spread']:.0f}个百分点。"
                    )
            
            results["analyses"].append(analysis)
        
        return results


    def _summarize_findings(self, df, results):
        findings = []

        # === 销售场景：关键指标优先 ===
        sales = results.get("sales_analysis")
        if sales and sales.get("存在"):
            sa = sales
            findings.append(
                f"[核心指标] 总销售额 {sa['总销售额']:,.0f} 元，总销量 {sa['总销量']:,} 件，"
                f"客单价均值 {sa['客单价均值']:,.0f} 元，"
                f"共 {sa['客户数']} 位客户购买 {sa['商品数']} 种商品。")

            best_day = sa.get("最佳销售日")
            if best_day:
                d = best_day
                detail_parts = [f"销售额 {d['销售额']:,.0f} 元"]
                if d.get("top商品"):
                    detail_parts.append(f"主力商品「{d['top商品']}」")
                if d.get("top客户"):
                    detail_parts.append(f"大客户「{d['top客户']}」")
                findings.append(f"[核心指标] 最佳销售日：{d['日期']}，{'，'.join(detail_parts)}。")

            worst_day = sa.get("最差销售日")
            if worst_day:
                findings.append(f"[核心指标] 最低销售日：{worst_day['日期']}，仅 {worst_day['销售额']:,.0f} 元。")

            top_prod_name = sa.get("top商品名称", "-")
            top_prod_amt = sa.get("top商品销售额", 0)
            top_prod_pct = sa.get("top商品占比", 0)
            top_cust_name = sa.get("top客户名称", "-")
            top_cust_spend = sa.get("top客户消费", 0)
            top_cust_pct = sa.get("top客户占比", 0)
            findings.append(
                f"[核心指标] TOP1 商品「{top_prod_name}」贡献 {top_prod_amt:,.0f} 元（占比 {top_prod_pct:.0f}%），"
                f"TOP1 客户「{top_cust_name}」消费 {top_cust_spend:,.0f} 元（占比 {top_cust_pct:.0f}%）。")

        findings.append(f"数据集共 {len(df)} 条记录，{len(df.columns)} 个字段。")

        missing_cols = [k for k,v in results["overview"]["缺失值"].items() if v>0]
        if missing_cols:
            findings.append(f"{len(missing_cols)} 个字段存在缺失值：{', '.join(missing_cols)}。")
        else:
            findings.append("数据质量良好，无缺失值。")

        if results["numeric_analysis"]["存在"]:
            for col in results["numeric_analysis"]["列"][:3]:
                mn, mx, avg = df[col].min(), df[col].max(), df[col].mean()
                findings.append(f"「{col}」：{mn:,.1f} ~ {mx:,.1f}，均值 {avg:,.1f}。")

        if results["numeric_analysis"].get("异常值"):
            for col, info in results["numeric_analysis"]["异常值"].items():
                findings.append(f"「{col}」存在 {info['数量']} 个离群值，建议核实。")

        if results["correlation"].get("强相关"):
            for p in results["correlation"]["强相关"]:
                findings.append(f"「{p['列1']}」与「{p['列2']}」呈{p['关系']}（r={p['相关系数']}），存在联动关系。")

        if results["category_analysis"]["存在"]:
            for col in results["category_analysis"]["列"][:2]:
                vc = df[col].value_counts()
                label, quantifier, _ = understand_field(col)
                findings.append(f"「{col}」共 {df[col].nunique()} {quantifier}{label}，"
                              f"「{vc.index[0]}」最多（{vc.iloc[0]}次，{vc.iloc[0]/len(df)*100:.0f}%）。")

        if results["time_analysis"]["存在"]:
            for col, info in results["time_analysis"]["详情"].items():
                findings.append(f"时间范围：{info['时间范围']}。")

        if self.semantics.field_roles:
            derived = [k for k,v in self.semantics.field_roles.items() if "计算字段" in str(v)]
            if derived:
                findings.append(f"提示：{', '.join(derived)} 是计算字段，与基础指标的相关性为数学派生关系。")


        # Smart rankings highlights
        sr = results.get("smart_rankings", {})
        if sr.get("exists") and sr.get("items"):
            for item in sr["items"][:4]:
                findings.append(item.get("insight", ""))

        return findings

    def _save_chart(self, fig, filename):
        path = os.path.join(self.chart_dir, filename)
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
        plt.close(fig)
        self.charts.append(path)
        return path


# ═══════════════ 便捷入口 ═══════════════

def run_analysis(filepath, output_dir="outputs"):
    # 智能检测表头行
    header_row, df_raw = detect_header_row(filepath)

    # 用检测到的表头行读取
    df = pd.read_excel(filepath, header=header_row)

    cleaner = DataCleaner()
    df_clean = cleaner.clean(df, filepath)

    analyzer = DataAnalyzer(output_dir=output_dir)
    results = analyzer.analyze(df_clean, os.path.basename(filepath), header_row)
    results["cleaning_log"] = cleaner.log
    results["charts_dir"] = analyzer.chart_dir


    return results








