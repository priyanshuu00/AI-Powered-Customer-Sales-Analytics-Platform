import plotly.express as px
import pandas as pd

class ChartBuilder:
    @staticmethod
    def line_chart(df: pd.DataFrame, x: str, y: str, title: str):
        return px.line(df, x=x, y=y, title=title, template="plotly_dark")
        
    @staticmethod
    def bar_chart(df: pd.DataFrame, x: str, y: str, title: str, color=None, orientation='v'):
        return px.bar(df, x=x, y=y, color=color, title=title, template="plotly_dark", orientation=orientation)
        
    @staticmethod
    def pie_chart(df: pd.DataFrame, names: str, values: str, title: str):
        return px.pie(df, names=names, values=values, title=title, template="plotly_dark")
        
    @staticmethod
    def treemap(df: pd.DataFrame, path: list, values: str, title: str):
        return px.treemap(df, path=path, values=values, title=title, template="plotly_dark")
