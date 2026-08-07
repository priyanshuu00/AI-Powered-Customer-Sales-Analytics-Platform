import pandas as pd
from .eda import DataProfiler
from .visualizations import Visualizer

class ProductAnalyzer:
    def __init__(self, profiler: DataProfiler):
        self.profiler = profiler
        self.order_items = profiler.load_table("order_items")
        self.products = profiler.load_table("products")
        self.translation = profiler.load_table("category_translation")

    def analyze(self) -> dict:
        if self.order_items.empty or self.products.empty:
            return {}

        df = pd.merge(self.order_items, self.products, on='product_id')
        if not self.translation.empty:
            df = pd.merge(df, self.translation, on='product_category_name', how='left')
            df['category'] = df['product_category_name_english']
        else:
            df['category'] = df['product_category_name']
            
        # Category Revenue
        cat_rev = df.groupby('category')['price'].sum().reset_index().sort_values('price', ascending=False)
        Visualizer.plot_bar_chart(cat_rev.head(10), 'category', 'price', 'Top 10 Categories by Revenue', 'category_revenue.png')
        
        top_cat = cat_rev.iloc[0]['category'] if not cat_rev.empty else "None"
        
        insights = {
            "top_category": top_cat,
            "top_category_revenue": cat_rev.iloc[0]['price'] if not cat_rev.empty else 0
        }
        return insights
