import pandas as pd
from .eda import DataProfiler
from .visualizations import Visualizer

class SalesAnalyzer:
    def __init__(self, profiler: DataProfiler):
        self.profiler = profiler
        self.orders = profiler.load_table("orders")
        self.payments = profiler.load_table("payments")
        
        # Merge orders and payments
        if not self.orders.empty and not self.payments.empty:
            self.sales_data = pd.merge(self.orders, self.payments, on='order_id')
            self.sales_data['order_purchase_timestamp'] = pd.to_datetime(self.sales_data['order_purchase_timestamp'])
        else:
            self.sales_data = pd.DataFrame()

    def analyze(self) -> dict:
        if self.sales_data.empty:
            return {}

        df = self.sales_data
        
        # Daily Revenue
        daily_rev = df.groupby(df['order_purchase_timestamp'].dt.date)['payment_value'].sum().reset_index()
        daily_rev.columns = ['date', 'revenue']
        Visualizer.plot_line_chart(daily_rev, 'date', 'revenue', 'Daily Revenue Trend', 'daily_revenue.png')
        
        # Monthly Revenue
        monthly_rev = df.groupby(df['order_purchase_timestamp'].dt.to_period('M'))['payment_value'].sum().reset_index()
        monthly_rev['order_purchase_timestamp'] = monthly_rev['order_purchase_timestamp'].astype(str)
        Visualizer.plot_bar_chart(monthly_rev, 'order_purchase_timestamp', 'payment_value', 'Monthly Revenue', 'monthly_revenue.png')
        
        top_month = monthly_rev.sort_values('payment_value', ascending=False).iloc[0]
        
        insights = {
            "total_revenue": df['payment_value'].sum(),
            "top_revenue_month": top_month['order_purchase_timestamp'],
            "top_month_revenue": top_month['payment_value']
        }
        return insights
