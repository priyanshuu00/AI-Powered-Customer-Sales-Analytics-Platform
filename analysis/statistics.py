import pandas as pd
import numpy as np

class StatAnalyzer:
    @staticmethod
    def compute_basic_stats(df: pd.DataFrame) -> dict:
        num_df = df.select_dtypes(include=[np.number])
        if num_df.empty:
            return {}
        
        stats = {
            "mean": num_df.mean().to_dict(),
            "median": num_df.median().to_dict(),
            "mode": df.mode().iloc[0].to_dict(),
            "std_dev": num_df.std().to_dict(),
            "variance": num_df.var().to_dict()
        }
        return stats

    @staticmethod
    def compute_percentiles(df: pd.DataFrame) -> dict:
        num_df = df.select_dtypes(include=[np.number])
        if num_df.empty:
            return {}
        return {
            "25th": num_df.quantile(0.25).to_dict(),
            "75th": num_df.quantile(0.75).to_dict()
        }
        
    @staticmethod
    def detect_outliers(df: pd.DataFrame, column: str) -> int:
        if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
            return 0
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        outliers = df[(df[column] < lower_bound) | (df[column] > upper_bound)]
        return len(outliers)
