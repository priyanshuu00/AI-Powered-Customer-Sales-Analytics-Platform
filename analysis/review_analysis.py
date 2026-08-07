import pandas as pd
from .eda import DataProfiler
from .visualizations import Visualizer

class ReviewAnalyzer:
    def __init__(self, profiler: DataProfiler):
        self.profiler = profiler
        self.reviews = profiler.load_table("reviews")

    def analyze(self) -> dict:
        if self.reviews.empty:
            return {}

        df = self.reviews
        
        # Rating Distribution
        rating_dist = df['review_score'].value_counts().reset_index()
        rating_dist.columns = ['score', 'count']
        Visualizer.plot_bar_chart(rating_dist, 'score', 'count', 'Review Score Distribution', 'review_scores.png')
        
        avg_rating = df['review_score'].mean()
        positive = len(df[df['review_score'] >= 4])
        negative = len(df[df['review_score'] <= 2])
        
        insights = {
            "average_rating": avg_rating,
            "positive_reviews_pct": (positive / len(df)) * 100,
            "negative_reviews_pct": (negative / len(df)) * 100
        }
        return insights
