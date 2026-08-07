import pandas as pd
from .eda import DataProfiler
from .visualizations import Visualizer

class PaymentAnalyzer:
    def __init__(self, profiler: DataProfiler):
        self.profiler = profiler
        self.payments = profiler.load_table("payments")

    def analyze(self) -> dict:
        if self.payments.empty:
            return {}

        df = self.payments
        
        # Payment Type
        ptype = df['payment_type'].value_counts().reset_index()
        ptype.columns = ['payment_type', 'count']
        Visualizer.plot_pie_chart(ptype, 'payment_type', 'count', 'Payment Type Distribution', 'payment_types.png')
        
        # Find dominant payment method
        dominant_type = ptype.iloc[0]['payment_type']
        dominant_pct = (ptype.iloc[0]['count'] / ptype['count'].sum()) * 100
        
        insights = {
            "dominant_payment_type": dominant_type,
            "dominant_payment_percentage": dominant_pct,
            "average_payment_value": df['payment_value'].mean()
        }
        return insights
