"""
Automatic Investment - Streamlit App (Refined, yfinance-only, MVC style)

Architecture:
- Model: data fetching and portfolio analytics
- View: Streamlit UI components
- Controller: connects View ↔ Model logic
"""
from controller import Controller

# -----------------------------
# Entrypoint
# -----------------------------
if __name__ == "__main__":
    controller = Controller()
    controller.run()
