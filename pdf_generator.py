"""
PDF 报告生成器 v4：Times New Roman 英文 + 彩色矩形条 + 统一编号颜色
"""
import os
from datetime import datetime
from fpdf import FPDF
from analyzer import understand_field

FONT_ZH = "C:/Windows/Fonts/simhei.ttf"
FONT_EN = "C:/Windows/Fonts/times.ttf"
FONT_EN_BOLD = "C:/Windows/Fonts/timesbd.ttf"


class PDFReport(FPDF):
    def __init__(self):
        super().__init__("P", "mm", "A4")
        self.set_auto_page_break(True, 12)
        # 中文
        self.add_font("zh", "", FONT_ZH, uni=True)
        self.add_font("zh", "B", FONT_ZH, uni=True)
        # 英文 Times New Roman
        self.add_font("en", "", FONT_EN, uni=True)
        self.add_font("en", "B", FONT_EN_BOLD, uni=True)

        self.C = {
            "dark":(26,54,93), "primary":(43,108,176), "red":(197,48,48),
            "green":(47,133,90), "orange":(221,107,32), "purple":(107,70,193),
            "lb":(235,245,255), "lr":(255,245,245), "lg":(240,255,245),
            "lgray":(248,249,252), "mgray":(230,235,242),
            "text":(50,50,50), "tlight":(130,130,140), "white":(255,255,255),
        }
        self._charts_dir = ""
        self.bar_colors = [
            (43,108,176),(197,48,48),(47,133,90),(221,107,32),(107,70,193),
            (49,130,206),(229,62,62),(56,161,105),(237,137,54),(128,90,213),
        ]

    def _banner(self, title, color):
        self.ln(2)
        self.set_fill_color(*color)
        self.set_text_color(*self.C["white"])
        self.set_font("zh", "B", 12)
        self.cell(0, 8, f"  {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.set_text_color(*self.C["text"])
        self.ln(2)

    def _text_zh(self, s, size=10, bold=False, color=None):
        self.set_font("zh", "B" if bold else "", size)
        if color: self.set_text_color(*color)
        self.multi_cell(0, size * 0.55, s, align="L")
        self.set_text_color(*self.C["text"])
        self.ln(1)

    def _text_en(self, s, size=11, bold=False, color=None):
        """英文用 Times New Roman，含中文自动切换"""
        if self._has_cjk(s):
            self.set_font("zh", "B" if bold else "", size)
        else:
            self.set_font("en", "B" if bold else "", size)
        if color: self.set_text_color(*color)
        self.multi_cell(0, 5.8, s, align="L")
        self.set_text_color(*self.C["text"])
        self.ln(1)

    def _has_cjk(self, s):
        """检测是否含有 CJK 字符"""
        for ch in str(s):
            cp = ord(ch)
            if (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
                0x20000 <= cp <= 0x2A6DF or 0xF900 <= cp <= 0xFAFF or
                0x2F800 <= cp <= 0x2FA1F):
                return True
        return False

    def _smart_multicell(self, w, s, line_h=6, align="L", fill=False, color=None, size=10, bold=False):
        """Smart multi_cell that handles mixed CJK/ASCII text with proper wrapping.
        CJK characters can break anywhere; ASCII words stay together."""
        if self._has_cjk(s):
            self.set_font("zh", "B" if bold else "", size)
        else:
            self.set_font("en", "B" if bold else "", size)
        if color:
            self.set_text_color(*color)
        # Use left-align to avoid stretched gaps
        self.multi_cell(w, line_h, s, align=align, fill=fill)
        self.set_text_color(*self.C["text"])

    def _smart_cell(self, w, h, s, align="L", new_x="LMARGIN", new_y="NEXT", bold=False, size=9):
        """智能选择字体：含中文用 zh，纯英文用 en"""
        if self._has_cjk(s):
            self.set_font("zh", "B" if bold else "", size)
        else:
            self.set_font("en", "B" if bold else "", size)
        self.cell(w, h, s, align=align, new_x=new_x, new_y=new_y)

    def _insight_box(self, text, color=None):
        if color is None:
            color = self.C["primary"]
        self.set_fill_color(*color)
        self.set_text_color(*color)
        self.set_font("zh", "B", 9.5)
        self.cell(3, 5.5, "")
        x0 = self.get_x()
        self.set_fill_color(*self.C["lgray"])
        self.set_text_color(*self.C["text"])
        if self._has_cjk(text):
            self.set_font("zh", "", 10)
        else:
            self.set_font("en", "", 10)
        self.set_x(x0+2)
        # Use wider multi_cell for better line wrapping
        self.multi_cell(172, 6, text, align="L", fill=True)
        self.ln(1.5)

    def _img(self, path, w=165, caption=""):
        if not os.path.exists(path):
            return
        try:
            from PIL import Image
            with Image.open(path) as img:
                iw, ih = img.size
            h = ih * (w / iw)
        except Exception:
            h = w * 0.55
        if self.get_y() + h > 275:
            self.add_page()
        x = (210 - w) / 2
        self.image(path, x=x, w=w, h=0)
        self.set_x(self.l_margin)
        self.ln(2)
        if caption:
            self.set_font("zh", "", 9)
            self.set_text_color(*self.C["tlight"])
            self.cell(0, 5.5, caption, align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(*self.C["text"])
            self.ln(1)

    def _ranking_table(self, title, items, value_label, accent_color, max_items=10):
        """Clean horizontal table: Rank | Name | Value"""
        if not items:
            return
        items = items[:max_items]
        w_rank, w_name, w_val = 10, 110, 55
        total_w = w_rank + w_name + w_val
        x0 = (210 - total_w) / 2
        row_h = 5.5

        # Title
        self.ln(2)
        self.set_font("en", "B", 10)
        self.set_text_color(*self.C["dark"])
        self.cell(0, 5.5, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

        # Header
        y0 = self.get_y()
        self.set_xy(x0, y0)
        self.set_fill_color(*accent_color)
        self.set_text_color(*self.C["white"])
        self.set_font("en", "B", 9)
        self.cell(w_rank, 6, "#", fill=True, align="C")
        self.cell(w_name, 6, "  Name", fill=True, align="L")
        self.cell(w_val, 6, value_label + "  ", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*self.C["text"])

        # Data rows
        for rank, (name, val) in enumerate(items, 1):
            y = self.get_y()
            bg = self.C["lgray"] if rank % 2 == 0 else self.C["white"]
            self.set_xy(x0, y)
            # Row background
            self.set_fill_color(*bg)
            # Rank number
            self.set_font("en", "B", 9)
            self.set_text_color(*self.C["tlight"])
            self.cell(w_rank, row_h, str(rank), fill=True, align="C")
            # Name
            short = str(name)[:22]
            if self._has_cjk(short):
                self.set_font("zh", "", 9.5)
            else:
                self.set_font("en", "", 9.5)
            self.set_text_color(*self.C["text"])
            self.cell(w_name, row_h, f"  {short}", fill=True, align="L")
            # Value
            self.set_font("en", "B", 7.5)
            self.set_text_color(*accent_color)
            self.cell(w_val, row_h, f"{val:,.0f}  ", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_text_color(*self.C["text"])
        self.ln(3)

    def _color_bars(self, freq_dict, max_w=90):
        items = list(freq_dict.items())[:10]
        if not items:
            return
        max_v = max(v for _, v in items)
        for idx, (label, val) in enumerate(items):
            self.set_font("zh", "", 8.5)
            self.set_text_color(*self.C["text"])
            short_label = str(label)[:10]
            self.cell(26, 4.5, f"  {short_label}")
            bar_w = max(4, int(val / max_v * max_w))
            color = self.bar_colors[idx % len(self.bar_colors)]
            self.set_fill_color(*color)
            self.set_text_color(*self.C["white"])
            self.set_font("zh", "B", 5.5)
            self.cell(bar_w, 4.5, f"{val} ", fill=True, align="R")
            self.set_fill_color(*self.C["white"])
            self.cell(max_w - bar_w, 4.5, "", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    # ── 封面 ──

    def _smart_new_page(self, needed_mm=30):
        """Only add new page if remaining space < needed_mm"""
        if self.get_y() + needed_mm > self.h - self.b_margin:
            self.add_page()

    def cover_page(self, title, filename, overview):
        self.add_page()
        self.set_fill_color(*self.C["dark"])
        self.rect(0, 0, 210, 65, "F")
        self.set_fill_color(*self.C["primary"])
        self.rect(0, 65, 210, 6, "F")
        self.set_fill_color(*self.C["orange"])
        self.rect(0, 71, 210, 3, "F")

        self.set_y(18)
        self.set_text_color(*self.C["white"])
        self.set_font("zh", "B", 24)
        self.cell(0, 12, title, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        # 英文副标题用 Times New Roman
        self.set_font("en", "", 13)
        self.cell(0, 7, "Automated Data Analysis Report", align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_y(82)
        self.set_text_color(*self.C["text"])
        items = [
            ("数据文件", filename),
            ("生成时间", datetime.now().strftime("%Y年%m月%d日 %H:%M")),
            ("数据规模", f"{overview['行数']} 条记录 | {overview['列数']} 个字段"),
        ]
        for k, v in items:
            self.set_fill_color(*self.C["lgray"])
            self.set_font("zh", "B", 11)
            self.cell(32, 7.5, f"  {k}", fill=True)
            self.set_font("zh", "", 9)
            self.cell(0, 7.5, v, new_x="LMARGIN", new_y="NEXT", fill=True)

    # ── 构建报告 ──
    def build_report(self, results, output_path):
        self._charts_dir = results.get("charts_dir", "outputs/charts")
        ov = results["overview"]

        self.cover_page(results["smart_title"], results["filename"], ov)

        # === Dashboard Page ===
        self.add_page()
        
        # Dashboard Header
        self.set_fill_color(*self.C["dark"])
        self.set_text_color(*self.C["white"])
        self.set_font("zh", "B", 13)
        self.cell(0, 9, f"  {results['smart_title']}  |  数据仪表盘", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(3)
        
        # KPI Cards Row
        total_rows = ov["行数"]
        total_cols = ov["列数"]
        missing_total = sum(ov["缺失值"].values())
        completeness = 100 - missing_total / max(total_rows * total_cols, 1) * 100
        num_cols_count = sum(1 for c in ov["列名"] if c in results.get("numeric_analysis", {}).get("列", []))
        cat_cols_count = sum(1 for c in ov["列名"] if c in results.get("category_analysis", {}).get("列", []))
        
        kpis = [
            (f"{total_rows:,}", "Records", self.C["dark"]),
            (f"{total_cols}", "Fields", self.C["primary"]),
            (f"{completeness:.0f}%", "Complete", self.C["green"]),
            (f"{num_cols_count}", "Numeric", self.C["orange"]),
            (f"{cat_cols_count}", "Category", self.C["purple"]),
        ]
        card_w = 33
        gap = 2
        total_w = card_w * len(kpis) + gap * (len(kpis) - 1)
        x_start = (210 - total_w) / 2
        y_kpi = self.get_y()
        
        for i, (val, label, color) in enumerate(kpis):
            x = x_start + i * (card_w + gap)
            self.set_xy(x, y_kpi)
            self.set_fill_color(*color)
            self.set_text_color(*self.C["white"])
            self.set_font("en", "B", 14)
            self.cell(card_w, 10, val, align="C", fill=True)
            self.set_xy(x, y_kpi + 10)
            self.set_fill_color(*self.C["lgray"])
            self.set_text_color(*self.C["text"])
            self.set_font("en", "", 9)
            self.cell(card_w, 5.5, label, align="C", fill=True)
        
        self.set_y(y_kpi + 18)
        
        # === Two-column layout: Left = Overview + Pie, Right = Quick Stats ===
        y_cols = self.get_y()
        
        # LEFT column: Overview insight
        self.set_fill_color(*self.C["lgray"])
        self.set_text_color(*self.C["text"])
        self.set_font("zh", "", 8)
        x_left = self.l_margin
        self.set_x(x_left + 2)
        self.multi_cell(100, 6, ov.get("insight", ""), fill=True)
        self.set_x(x_left)
        y_after_insight = self.get_y()
        
        # LEFT column: Pie chart below insight
        chart = os.path.join(self._charts_dir, "overview_types.png")
        if os.path.exists(chart):
            try:
                from PIL import Image
                with Image.open(chart) as img:
                    iw, ih = img.size
                w = 90
                h = ih * (w / iw)
                self.set_y(max(y_after_insight + 3, self.get_y()))
                self.image(chart, x=15, w=w, h=h)
                self.ln(1)
                self.set_font("zh", "", 9)
                self.set_text_color(*self.C["tlight"])
                self.cell(w, 4, "Field Type Distribution", align="C", new_x="LMARGIN", new_y="NEXT")
                self.set_text_color(*self.C["text"])
            except Exception:
                pass
        
        # RIGHT column: Quick Stats panel
        right_x = 115
        self.set_xy(right_x, y_cols)
        self.set_fill_color(*self.C["dark"])
        self.set_text_color(*self.C["white"])
        self.set_font("zh", "B", 8)
        self.cell(80, 6, "  Quick Stats", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*self.C["text"])
        self.ln(1)
        
        # Numeric field stats
        na = results.get("numeric_analysis", {})
        if na.get("存在") and na.get("列"):
            self.set_x(right_x)
            self.set_font("zh", "B", 11)
            self.set_text_color(*self.C["primary"])
            self.cell(80, 5, "  Numeric Fields", new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(*self.C["text"])
            import numpy as np
            for col in na["列"][:5]:
                stats = na.get("统计", {}).get(col, {})
                mn = stats.get("mean", 0)
                mx = stats.get("max", 0)
                if isinstance(mn, (int, float, np.floating)) and isinstance(mx, (int, float, np.floating)):
                    short = str(col)[:16]
                    self.set_x(right_x + 2)
                    self.set_font("zh", "", 8.5)
                    self.cell(38, 4.2, short)
                    self.set_font("en", "", 8.5)
                    self.cell(38, 4.2, f"{float(mn):,.1f} ~ {float(mx):,.1f}", align="R", new_x="LMARGIN", new_y="NEXT")
        
        # Category field stats
        ca = results.get("category_analysis", {})
        if ca.get("存在") and ca.get("列"):
            self.ln(1)
            self.set_x(right_x)
            self.set_font("zh", "B", 11)
            self.set_text_color(*self.C["orange"])
            self.cell(80, 5, "  Category Fields", new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(*self.C["text"])
            for col in ca["列"][:5]:
                detail = ca.get("详情", {}).get(col, {})
                nu = detail.get("唯一值数", "?")
                freq = detail.get("频次", {})
                top_name = list(freq.keys())[0] if freq else "?"
                short = str(col)[:12]
                self.set_x(right_x + 2)
                self.set_font("zh", "", 8.5)
                self.cell(38, 4.2, short)
                self.set_font("en", "", 8)
                self.cell(38, 4.2, f"{nu} cats, top: {str(top_name)[:10]}", align="R", new_x="LMARGIN", new_y="NEXT")
        
        # Correlation highlights
        corr = results.get("correlation", {})
        strong = corr.get("强相关", [])
        if strong:
            self.ln(1)
            self.set_x(right_x)
            self.set_font("zh", "B", 11)
            self.set_text_color(*self.C["dark"])
            self.cell(80, 5, "  Top Correlations", new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(*self.C["text"])
            for p in strong[:3]:
                self.set_x(right_x + 2)
                a_short = str(p["列1"])[:10]
                b_short = str(p["列2"])[:10]
                r_val = p["相关系数"]
                self.set_font("zh", "", 8.5)
                self.cell(60, 4.2, f"{a_short} vs {b_short}")
                sign = "+" if r_val > 0 else ""
                self.set_font("en", "B", 9)
                self.set_text_color(*self.C["red"] if r_val < 0 else self.C["green"])
                self.cell(16, 4.2, f"r={sign}{r_val:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
                self.set_text_color(*self.C["text"])
        
        # Binary outcome preview
        bo = results.get("binary_outcome", {})
        if bo.get("exists") and bo.get("analyses"):
            self.ln(1)
            self.set_x(right_x)
            self.set_font("zh", "B", 11)
            self.set_text_color(*self.C["red"])
            self.cell(80, 5, "  Key Outcome", new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(*self.C["text"])
            for a in bo["analyses"]:
                self.set_x(right_x + 2)
                self.set_font("zh", "", 9)
                self.cell(38, 5, str(a["column"])[:14])
                self.set_font("en", "B", 9)
                pr = a["pass_rate"]
                color = self.C["green"] if pr >= 50 else self.C["red"]
                self.set_text_color(*color)
                self.cell(38, 5, f"{pr:.0f}% Pass", align="R", new_x="LMARGIN", new_y="NEXT")
                self.set_text_color(*self.C["text"])
        
        # Reset position
        self.set_x(self.l_margin)
        self.set_y(max(self.get_y() + 4, y_cols + 130))
        
        # Key Highlights section at bottom
        findings = results.get("key_findings", [])
        if findings:
            self._banner("Key Highlights", self.C["primary"])
            for f in findings[:5]:
                self.set_fill_color(*self.C["lgray"])
                self.set_text_color(*self.C["tlight"])
                self.set_font("en", "B", 9)
                idx = findings.index(f)
                self.cell(6, 5, f" {idx+1}", fill=True)
                self.set_fill_color(*self.C["white"])
                self.set_text_color(*self.C["text"])
                self.set_font("zh", "", 9.5)
                self.multi_cell(168, 5.8, f, fill=True)
                self.ln(1)
        
        # Cleaning footnote
        clog = results.get("cleaning_log", [])
        if clog:
            self.ln(2)
            summary = " | ".join([f"{s['步骤']}: {s['详情']}" for s in clog])
            self.set_font("zh", "", 8)
            self.set_text_color(*self.C["tlight"])
            self.cell(0, 4, f"Data Cleaning: {summary}", new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(*self.C["text"])


        # === 销售场景深度分析（图片优先） ===
        sales = results.get("sales_analysis", {})
        if sales.get("存在"):
            self.add_page()
            self._banner("Sales Key Metrics", self.C["red"])

            # 关键数字卡片
            y_start = self.get_y()
            metrics = [
                ("Total Revenue", f"{sales.get("总销售额", 0):,.0f}", self.C["dark"]),
                ("Total Quantity", f"{sales.get("总销量", 0):,}", self.C["primary"]),
                ("Avg Order Value", f"{sales.get("客单价均值", 0):,.0f}", self.C["green"]),
                ("Customers", str(sales.get("客户数", 0)), self.C["orange"]),
                ("Products", str(sales.get("商品数", 0)), self.C["purple"]),
                ("Transactions", str(sales.get("记录数", 0)), self.C["dark"]),
            ]
            card_w = 30
            gap = 2
            x_start = (210 - (card_w * 6 + gap * 5)) / 2
            for i, (label, value, color) in enumerate(metrics):
                x = x_start + i * (card_w + gap)
                self.set_xy(x, y_start)
                self.set_fill_color(*color)
                self.set_text_color(*self.C["white"])
                # value
                self.set_font("en", "B", 13)
                self.cell(card_w, 8, value, align="C", fill=True)
                # label
                self.set_xy(x, y_start + 8)
                self.set_fill_color(*self.C["lgray"])
                self.set_text_color(*self.C["text"])
                self.set_font("en", "", 8.5)
                self.cell(card_w, 5, label, align="C", fill=True)
            self.set_y(y_start + 18)

            # 最佳/最差销售日
            best_day = sales.get("最佳销售日")
            worst_day = sales.get("最差销售日")
            if best_day or worst_day:
                self.set_font("en", "B", 10)
                self.set_text_color(*self.C["dark"])
                self.cell(0, 5, "Daily Highlights", new_x="LMARGIN", new_y="NEXT")
                self.set_text_color(*self.C["text"])
                self.set_font("en", "", 9.5)
                if best_day:
                    parts = [f"Best: {best_day.get("日期", "?")} ({best_day.get("销售额", 0):,.0f})"]
                    if best_day.get("top商品"):
                        parts.append(f"| Top product: {best_day.get("top商品", "?")}")
                    if best_day.get("top客户"):
                        parts.append(f"| Top customer: {best_day.get("top客户", "?")}")
                    text = "  ".join(parts)
                    if self._has_cjk(text):
                        self.set_font("zh", "", 9.5)
                    self.multi_cell(0, 5.5, text)
                if worst_day:
                    self.set_x(self.l_margin)
                    self.multi_cell(0, 4.5, f"Slowest: {worst_day.get("日期", "?")} ({worst_day.get("销售额", 0):,.0f})")
                self.ln(2)

            # 每日趋势图
            daily_chart = sales.get("每日趋势图")
            if daily_chart:
                self._banner("Daily Sales Trend", self.C["primary"])
                self._img(daily_chart, w=180)

            # 商品排名图
            product_chart = sales.get("商品排名图")
            if product_chart:
                self._banner("Product Ranking", self.C["green"])
                self._img(product_chart, w=180)
                # 商品排名表格
                prod_rank = sales.get("商品排名", {})
                if prod_rank:
                    self._ranking_table("Top Products by Revenue", list(prod_rank.items()), "Revenue", self.C["green"])

            # 客户排名图
            customer_chart = sales.get("客户排名图")
            if customer_chart:
                self._banner("Customer Ranking", self.C["orange"])
                self._img(customer_chart, w=180)
                # 客户排名表格
                cust_rank = sales.get("客户排名", {})
                if cust_rank:
                    self._ranking_table("Top Customers by Spend", list(cust_rank.items()), "Spend", self.C["orange"])

        na = results.get("numeric_analysis", {})
        if na.get("存在"):
            self._smart_new_page(45)
            self._banner("数值字段深度分析", self.C["green"])
            self._text_zh("以下展示各数值字段的分布形态与统计特征，揭示数据的集中趋势、离散程度及潜在异常。", 9.5)
            for col in na["列"][:3]:
                chart = na.get("图表", {}).get(col)
                insight = na.get("洞察", {}).get(col, "")
                if chart:
                    self._img(chart, w=170, caption=f"{col} Distribution Histogram")
                if insight:
                    self._insight_box(f"[{col}] {insight}", self.C["green"])
                if col in na.get("异常值", {}):
                    n = na["异常值"][col]["数量"]
                    self._text_zh(f"[!] {col} 存在 {n} 个离群值，建议核实。", 9, color=self.C["red"])
            boxplot = na.get("图表", {}).get("箱线图")
            if boxplot:
                self._img(boxplot, w=170, caption="数值字段箱线图对比")

        # === 第2页 ===
        self.add_page()

        ca = results.get("category_analysis", {})
        if ca.get("存在"):
            self._banner("分类字段分析", self.C["orange"])
            self._text_zh("以下分析各分类字段的构成与分布，揭示数据在不同维度上的聚集特征与长尾效应。", 9.5)
            for col in ca["列"][:2]:
                detail = ca.get("详情", {}).get(col, {})
                freq = detail.get("频次", {})
                chart = detail.get("图表")
                if chart:
                    self._img(chart, w=170)
                if freq:
                    self._color_bars(freq, max_w=80)
                insight = detail.get("洞察", "")
                if insight:
                    self._insight_box(f"[{col}] {insight}", self.C["orange"])

        ta = results.get("time_analysis", {})
        if ta.get("存在"):
            self._banner("时间趋势", self.C["purple"])
            for col_name, info in ta.get("详情", {}).items():
                chart = info.get("趋势图")
                if chart:
                    self._img(chart, w=170)
                insight = info.get("洞察", "")
                if insight:
                    self._insight_box(insight, self.C["purple"])

        corr = results.get("correlation", {})
        if corr.get("存在"):
            self._banner("字段相关性", self.C["dark"])
            chart = corr.get("热力图")
            if chart:
                self._img(chart, w=90)
            insight = corr.get("洞察", "")
            if insight:
                self._insight_box(insight, self.C["dark"])

        # === Binary Outcome Analysis ===
        bo = results.get("binary_outcome", {})
        if bo.get("exists") and bo.get("analyses"):
            self._smart_new_page(35)
            self._banner("关键指标深度分析", self.C["red"])
            for analysis in bo["analyses"]:
                col_name = analysis["column"]
                pos_label = analysis["positive_label"]
                neg_label = analysis["negative_label"]
                pass_rate = analysis["pass_rate"]
                pos_count = analysis["positive_count"]
                neg_count = analysis["negative_count"]
                total = pos_count + neg_count
                
                # Pass Rate KPI
                self.ln(2)
                self.set_font("zh", "B", 11)
                self.set_text_color(*self.C["text"])
                self.cell(0, 6, f"{col_name} 通过率分析", new_x="LMARGIN", new_y="NEXT")
                self.ln(1)
                
                # Big pass rate display
                self.set_fill_color(*self.C["dark"])
                self.set_text_color(*self.C["white"])
                self.set_font("en", "B", 16)
                y_pr = self.get_y()
                self.cell(50, 12, f"  {pass_rate:.1f}%", fill=True)
                self.set_font("zh", "", 9.5)
                self.cell(50, 12, f"  {pos_label}: {pos_count} | {neg_label}: {neg_count}", fill=True, new_x="LMARGIN", new_y="NEXT")
                self.ln(2)
                
                # Insight
                insight = analysis.get("insight", "")
                if insight:
                    self._insight_box(insight, self.C["red"])
                
                # Comparison chart
                comp_chart = analysis.get("comparison_chart")
                if comp_chart:
                    self._img(comp_chart, w=170, caption=f"{pos_label} vs {neg_label}: Key Metric Differences")
                
                # Category breakdowns
                cat_insight = analysis.get("cat_insight", "")
                if cat_insight:
                    self._insight_box(cat_insight, self.C["orange"])
                
                cat_breakdowns = analysis.get("category_breakdowns", [])
                for cb in cat_breakdowns[:2]:
                    chart = cb.get("chart")
                    if chart:
                        self._img(chart, w=170, caption=f"Pass Rate by {cb['category_field']}")

        cross = results.get("cross_analysis", {})
        if cross.get("存在") and cross.get("分析"):
            self._banner("交叉分析", self.C["primary"])
            for item in cross["分析"]:
                chart = item.get("图表")
                if chart:
                    self._img(chart, w=170)
                insight = item.get("洞察", "")
                if insight:
                    self._insight_box(insight, self.C["primary"])

        # === 第3页：关键发现 ===
        self.add_page()
        

        # === Smart Rankings ===
        sr = results.get("smart_rankings", {})
        if sr.get("exists") and sr.get("items"):
            self._smart_new_page(40)
            self._banner("Key Rankings", self.C["primary"])
            for item in sr["items"]:
                chart = item.get("chart")
                insight = item.get("insight", "")
                rank_data = item.get("rank_data", {})
                dim = item.get("dim", "")
                meas = item.get("meas", "")
                if chart:
                    self._img(chart, w=175)
                if insight:
                    self._insight_box(insight, self.C["primary"])
                if rank_data:
                    items = list(rank_data.items())
                    if items:
                        self._ranking_table(f"Top {dim} by {meas}", items, meas, self.C["primary"])

        self._banner("关键发现与建议", self.C["red"])

        findings = results.get("key_findings", [])
        # 统一灰色编号
        for i, f in enumerate(findings):
            self.set_fill_color(*self.C["lgray"])
            self.set_text_color(*self.C["tlight"])
            self.set_font("zh", "B", 10)
            self.cell(8, 6, f" {i+1}", fill=True)
            self.set_text_color(*self.C["text"])
            self.set_font("zh", "", 10)
            self.multi_cell(0, 6, f, fill=True)
            self.ln(1)

        self.ln(4)
        self.set_draw_color(*self.C["mgray"])
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(3)
        self.set_font("zh", "", 8)
        self.set_text_color(*self.C["tlight"])
        self.cell(0, 5, f"Report end | Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.output(output_path)
        return output_path


def generate_pdf(results, output_path):
    pdf = PDFReport()
    return pdf.build_report(results, output_path)
