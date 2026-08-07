import pandas as pd
from .eda import DataProfiler
from .visualizations import Visualizer

class CustomerAnalyzer:
    def __init__(self, profiler: DataProfiler):
        self.profiler = profiler
        self.customers = profiler.load_table("customers")
        self.orders = profiler.load_table("orders")
        self.payments = profiler.load_table("payments")

    def analyze(self) -> dict:
        if self.customers.empty or self.orders.empty or self.payments.empty:
            return {}

        df = pd.merge(self.customers, self.orders, on='customer_id')
        df = pd.merge(df, self.payments, on='order_id')
        
        # Customer spend
        customer_spend = df.groupby('customer_unique_id').agg(
            total_spent=('payment_value', 'sum'),
            order_count=('order_id', 'nunique')
        ).reset_index()
        
        # Repeat customers
        repeat_customers = customer_spend[customer_spend['order_count'] > 1]
        repeat_pct = (len(repeat_customers) / len(customer_spend)) * 100
        repeat_rev_pct = (repeat_customers['total_spent'].sum() / customer_spend['total_spent'].sum()) * 100
        
        # Geographic
        state_dist = self.customers['customer_state'].value_counts().reset_index()
        state_dist.columns = ['state', 'count']
        Visualizer.plot_bar_chart(state_dist.head(10), 'state', 'count', 'Top 10 States by Customers', 'customer_states.png')
        
        insights = {
            "total_customers": len(customer_spend),
            "repeat_customer_rate": repeat_pct,
            "repeat_customer_revenue_contribution": repeat_rev_pct,
            "average_clv": customer_spend['total_spent'].mean()
        }
        return insights
