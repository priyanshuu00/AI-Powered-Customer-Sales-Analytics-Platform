import pandas as pd
import base64

def get_csv_download_link(df: pd.DataFrame, filename: str, button_text: str):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}" class="btn btn-primary" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">{button_text}</a>'
    return href
