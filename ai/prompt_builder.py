class PromptBuilder:
    @staticmethod
    def build_executive_summary_prompt(metrics: dict) -> str:
        return f"""
        Act as a Senior Business Analyst. Based on the following e-commerce KPIs, generate an executive summary.
        Data: {metrics}
        Include:
        - Overall business performance
        - Major achievements
        - Major risks
        - Business health score (out of 100)
        """
        
    @staticmethod
    def build_insights_prompt(domain: str, data: dict) -> str:
        return f"""
        Act as a Senior Data Scientist. Analyze the following {domain} data and extract 3-5 specific business insights.
        Data: {data}
        Format as bullet points. Examples: "Revenue dropped 12%", "Average delivery time improved".
        Also include a Root Cause Analysis section identifying possible reasons for any negative trends (e.g., "Sales decreased because of high delivery delay").
        """
        
    @staticmethod
    def build_recommendations_prompt(insights: str) -> str:
        return f"""
        Act as a Chief Strategy Officer. Based on the following business insights, generate 3-5 actionable business recommendations.
        Insights: {insights}
        Format as bullet points. Examples: "Increase inventory", "Launch loyalty campaign".
        """
        
    @staticmethod
    def build_chat_prompt(question: str, context: dict) -> str:
        return f"""
        Act as an AI Business Intelligence Assistant. Answer the user's question clearly and concisely using the provided context.
        Context: {context}
        User Question: {question}
        """
