import os
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Optional

CHARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

class Visualizer:
    @staticmethod
    def save_plot(filename: str):
        filepath = os.path.join(CHARTS_DIR, filename)
        plt.savefig(filepath, bbox_inches='tight')
        plt.close()
        return filepath

    @staticmethod
    def plot_line_chart(df: pd.DataFrame, x: str, y: str, title: str, filename: str):
        plt.figure(figsize=(10, 6))
        sns.lineplot(data=df, x=x, y=y)
        plt.title(title)
        plt.xticks(rotation=45)
        return Visualizer.save_plot(filename)
        
    @staticmethod
    def plot_bar_chart(df: pd.DataFrame, x: str, y: str, title: str, filename: str):
        plt.figure(figsize=(10, 6))
        sns.barplot(data=df, x=x, y=y)
        plt.title(title)
        plt.xticks(rotation=45)
        return Visualizer.save_plot(filename)
        
    @staticmethod
    def plot_pie_chart(df: pd.DataFrame, names: str, values: str, title: str, filename: str):
        fig = px.pie(df, names=names, values=values, title=title)
        filepath = os.path.join(CHARTS_DIR, filename.replace('.png', '.html'))
        fig.write_html(filepath)
        return filepath
        
    @staticmethod
    def plot_histogram(df: pd.DataFrame, x: str, title: str, filename: str):
        plt.figure(figsize=(10, 6))
        sns.histplot(data=df, x=x, bins=30, kde=True)
        plt.title(title)
        return Visualizer.save_plot(filename)
        
    @staticmethod
    def plot_heatmap(df: pd.DataFrame, title: str, filename: str):
        plt.figure(figsize=(10, 8))
        sns.heatmap(df.corr(numeric_only=True), annot=True, cmap='coolwarm', fmt='.2f')
        plt.title(title)
        return Visualizer.save_plot(filename)
