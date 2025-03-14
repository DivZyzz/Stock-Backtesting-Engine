import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import datetime
import plotly.graph_objs as go
import plotly.express as px

# Streamlit App Title and Description
st.title("Stock Backtesting Engine")
st.markdown(""" 
This application allows you to backtest stock strategies using historical data. 
Select a stock, set the parameters, and analyze the performance of various trading strategies. **Developed by [Divyanshu Yadav](https://github.com/DivZyzz)** 
""")

# Stock Options Dictionary
stock_options = {
    "Dow Jones Industrial Average": "^DJI",
    "S&P 500": "^GSPC",
    "Nasdaq Composite": "^IXIC",
    "Nifty50": "^NSEI",
    "Bank Nifty": "^NSEBANK",
    "Sensex": "^BSESN",
    "Nikkei 225": "^N225"
}

# Sidebar for stock selection
st.sidebar.subheader("1. Select Stock Data")
selected_stock_names = st.sidebar.multiselect("Select Stocks", list(stock_options.keys()), default=list(stock_options.keys())[0])
# Backtest Configuration Inputs
st.sidebar.subheader("2. Backtest Configuration")
st.sidebar.markdown("### Portfolio Allocation")
allocation = {}
for stock in selected_stock_names:
    allocation[stock] = st.sidebar.slider(
        f"Allocation for {stock} (%)", min_value=0, max_value=100, value=100 // len(selected_stock_names)
        )
# Ensure that the total allocation is 100%
if sum(allocation.values()) != 100:
    st.sidebar.error("Total allocation must be 100%!")
else:
    # Dictionary to store each stock's backtest results
    portfolio_results = {}
    
    
initial_capital = st.sidebar.number_input("Initial Capital", min_value=1000, step=1000)
start_date = st.sidebar.text_input("Start Date (YYYY-MM-DD)", "2023-01-01")
end_date = st.sidebar.text_input("End Date (YYYY-MM-DD)", "2024-01-01")
investment_type = st.sidebar.selectbox("Investment Style", ["Aggressive", "Moderate", "Passive"])
strategy_type = st.sidebar.selectbox("Select Strategy", ["Moving Average Crossover", "Bollinger Bands", "Combined"])
transaction_cost = st.sidebar.number_input("Transaction Cost (%)", value=0.1) / 100
stop_loss_pct = st.sidebar.number_input("Stop Loss (%)", value=5) / 100
take_profit_pct = st.sidebar.number_input("Take Profit (%)", value=10) / 100

if st.sidebar.button("Run Backtest"):
    with st.spinner("Running backtest..."):
        def backtest(stock_symbol, initial_capital, start_date, end_date, investment_type, strategy_type, transaction_cost=0.001, stop_loss_pct=0.05, take_profit_pct=0.10):
            # Load and prepare the data
            df = yf.download(stock_symbol, start='1992-01-01')
            df.reset_index(inplace=True)
            expected_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
            if len(df.columns) == 6:
                df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            elif len(df.columns) == 7: 
                df.columns = expected_columns
            else:
                st.error(f"Unexpected number of columns: {len(df.columns)}. Expected 6 or 7 columns.")
                return  # Exit the function if the columns don't match
             
             #df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce', utc=True)
            df = df.dropna(subset=['Date'])
            # Add these lines above the existing line 50
            start_date = pd.to_datetime(start_date).tz_localize('UTC')
            end_date = pd.to_datetime(end_date).tz_localize('UTC')

            # Replace line 50 with the following line
            df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
            if df.empty:
                 st.error(f"No data available for {stock_symbol} between {start_date} and {end_date}.")
                 return

            df.set_index('Date', inplace=True)
            st.write("**Selected Stock Data:**", df)
        
            # Rest of the backtest function remains the same...

            # Moving average crossover settings
            short_window = 40
            long_window = 100
            df['Short_MA'] = df['Close'].rolling(window=short_window, min_periods=1).mean()
            df['Long_MA'] = df['Close'].rolling(window=long_window, min_periods=1).mean()

            # Bollinger Bands settings based on investment type
            if investment_type == 'Aggressive':
                window, num_std = 15, 2.5
            elif investment_type == 'Moderate':
                window, num_std = 20, 2
            else:  # Passive
                window, num_std = 30, 1.5

            # Bollinger Bands calculations
            df['Rolling_Mean'] = df['Close'].rolling(window=window, min_periods=1).mean()
            df['Rolling_Std'] = df['Close'].rolling(window=window, min_periods=1).std()
            df['Upper_Band'] = df['Rolling_Mean'] + (df['Rolling_Std'] * num_std)
            df['Lower_Band'] = df['Rolling_Mean'] - (df['Rolling_Std'] * num_std)

            # Generate buy/sell signals based on chosen strategy
            df['Signal'] = 0  # Initialize signal column

            if strategy_type == 'Moving Average Crossover':
                df['Signal'] = np.where(df['Short_MA'] > df['Long_MA'], 1, 0)  # Moving Average crossover
            elif strategy_type == 'Bollinger Bands':
                df['Signal'] = np.where(df['Close'] < df['Lower_Band'], 1, 0)  # Bollinger Buy
                df['Signal'] = np.where(df['Close'] > df['Upper_Band'], -1, df['Signal'])  # Bollinger Sell
            elif strategy_type == 'Combined':
                bollinger_signal = np.where(df['Close'] < df['Lower_Band'], 1, 0)
                bollinger_signal = np.where(df['Close'] > df['Upper_Band'], -1, bollinger_signal)
                ma_signal = np.where(df['Short_MA'] > df['Long_MA'], 1, 0)
                #df['Signal'] = np.where((bollinger_signal == 1) & (ma_signal == 1), 1, 0)
                #df['Signal'] = np.where((bollinger_signal == -1) & (ma_signal == 0), -1, df['Signal'])
                df['Signal'] = np.where((bollinger_signal == 1) | (ma_signal == 1), 1, 0)  # Buy signal if either is true
                df['Signal'] = np.where((bollinger_signal == -1) | (ma_signal == 0), -1, df['Signal']) 

            # Calculate daily returns
            df['Returns'] = df['Close'].pct_change().fillna(0)

            # Initialize variables for tracking
            portfolio_value = initial_capital
            df['Portfolio_Value'] = initial_capital  # Initialize with initial capital
            position = 0  # 1 for long, -1 for short, 0 for no position
            buy_price = 0
            trades = []
            wins = 0
            losses = 0
            trade_profits = []

            # Iterate over the DataFrame to handle trades based on signals
            for i in range(1, len(df)):
                date = df.index[i]
                signal = df['Signal'].iloc[i]
                price = df['Close'].iloc[i]
                previous_position = position
                
                # Check for existing position and signal
                if position == 0:
                    if signal == 1:  # Buy Signal
                        position = 1
                        buy_price = price
                        portfolio_value -= transaction_cost * portfolio_value  # Apply transaction cost
                        # Set stop-loss and take-profit
                        current_stop_loss = buy_price * (1 - stop_loss_pct)
                        current_take_profit = buy_price * (1 + take_profit_pct)
                        trades.append({'Type': 'Buy', 'Price': buy_price, 'Date': date})
                
                elif position == 1:  # Already in long position
                    # Check for stop-loss, take-profit, or sell signal
                    if price <= current_stop_loss:  # Stop-Loss Triggered
                        sell_price = current_stop_loss
                        profit = (sell_price - buy_price) / buy_price - transaction_cost
                        portfolio_value *= (1 + profit)
                        portfolio_value -= transaction_cost * portfolio_value  # Apply transaction cost
                        position = 0
                        trades.append({'Type': 'Sell', 'Price': sell_price, 'Date': date, 'Profit': profit})
                        if profit > 0:
                            wins += 1
                        else:
                            losses += 1
                        trade_profits.append(profit)
                    elif price >= current_take_profit:  # Take-Profit Triggered
                        sell_price = current_take_profit
                        profit = (sell_price - buy_price) / buy_price - transaction_cost
                        portfolio_value *= (1 + profit)
                        portfolio_value -= transaction_cost * portfolio_value  # Apply transaction cost
                        position = 0
                        trades.append({'Type': 'Sell', 'Price': sell_price, 'Date': date, 'Profit': profit})
                        if profit > 0:
                            wins += 1
                        else:
                            losses += 1
                        trade_profits.append(profit)
                    elif signal == -1:  # Sell Signal
                        sell_price = price
                        profit = (sell_price - buy_price) / buy_price - transaction_cost
                        portfolio_value *= (1 + profit)
                        portfolio_value -= transaction_cost * portfolio_value  # Apply transaction cost
                        position = 0
                        trades.append({'Type': 'Sell', 'Price': sell_price, 'Date': date, 'Profit': profit})
                        if profit > 0:
                            wins += 1
                        else:
                            losses += 1
                        trade_profits.append(profit)
                
                # Update portfolio value based on returns if holding position
                if position == 1:
                    portfolio_value *= (1 + df['Returns'].iloc[i])
                
                # Assign the updated portfolio value to the DataFrame
                df.loc[date, 'Portfolio_Value'] = portfolio_value
            
            # If still in position at the end, close it
            if position == 1:
                sell_price = df['Close'].iloc[-1]
                profit = (sell_price - buy_price) / buy_price - transaction_cost
                portfolio_value *= (1 + profit)
                portfolio_value -= transaction_cost * portfolio_value  # Apply transaction cost
                position = 0
                trades.append({'Type': 'Sell', 'Price': sell_price, 'Date': df.index[-1], 'Profit': profit})
                if profit > 0:
                    wins += 1
                else:
                    losses += 1
                trade_profits.append(profit)
                df.loc[df.index[-1], 'Portfolio_Value'] = portfolio_value
            
            # Fill any remaining portfolio value cells
            df['Portfolio_Value'] = df['Portfolio_Value'].ffill()
            
            # Calculate HODL value
            df['HODL_Value'] = initial_capital * (df['Close'] / df['Close'].iloc[0])

            
            # Performance metrics
            total_return = (portfolio_value - initial_capital) / initial_capital
            total_return_percent = total_return * 100
            if len(trade_profits) > 0:
                avg_profit_per_trade = np.mean(trade_profits)
            else:
                avg_profit_per_trade = 0
            if losses > 0:
                win_loss_ratio = wins / losses
            else:
                win_loss_ratio = wins
            if len(trade_profits) > 1 and np.std(trade_profits) != 0:
                sharpe_ratio = (np.mean(trade_profits) / np.std(trade_profits)) * np.sqrt(252)
            else:
                sharpe_ratio = 0
            max_drawdown = (df['Portfolio_Value'].cummax() - df['Portfolio_Value']).max() / df['Portfolio_Value'].cummax().max() if df['Portfolio_Value'].cummax().max() > 0 else 0
            
            # Calculate annualized return
            days = (end_date - start_date).days
            if days > 0:
                annualized_return = (1 + total_return) ** (252 / days) - 1
            else:
                annualized_return = 0
            
            hodl_return = df['Close'].iloc[-1] / df['Close'].iloc[0] - 1
            strategy_return = portfolio_value / initial_capital - 1
            is_profitable = strategy_return > hodl_return

            # Displaying a summary box based on the profitability comparison
            if strategy_return > 0:
                if is_profitable:
                    st.success(f"Your strategy outperformed the HODL strategy with a profit of ${portfolio_value - initial_capital:,.2f}!")
                else:
                    st.info(f"Your strategy was profitable with a gain of ${portfolio_value - initial_capital:,.2f}, but did not outperform the HODL strategy.")
            else:
                st.error(f"Your strategy resulted in a loss of ${abs(portfolio_value - initial_capital):,.2f}. Consider revising the strategy.")
                
                    
                
            # Output summary
            st.markdown(f"### Backtest Summary for {stock_symbol.replace(' ', '_')}:")         
            st.write(f"Strategy Type: {strategy_type}")
            st.write(f"Initial Capital: ${initial_capital:,.2f}")
            #st.write(f"Final Portfolio Value: ${portfolio_value:.2f}")
            if initial_capital<portfolio_value:
                st.markdown(f"**Final Portfolio Value:** <span style='color:green;'>${portfolio_value:.2f}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"**Final Portfolio Value:** <span style='color:red;'>${portfolio_value:.2f}</span>", unsafe_allow_html=True)
            st.write(f"{'Profit' if total_return > 0 else 'Loss'}: ${abs(portfolio_value - initial_capital):,.2f}")
            st.write(f"Total Return: {total_return_percent:.2f}%")
            st.write(f"Sharpe Ratio: {sharpe_ratio:.2f}")
            st.write(f"Max Drawdown: {max_drawdown * 100:.2f}%")
            st.write(f"Annualized Return: {annualized_return * 100:.2f}%")
            st.write(f"Total Trades: {len(trade_profits)}")
            st.write(f"Winning Trades: {wins}")
            st.write(f"Losing Trades: {losses}")
            st.write(f"Win/Loss Ratio: {win_loss_ratio:.2f}")
            st.write(f"Average Profit per Trade: {avg_profit_per_trade * 100:.2f}%")
        


            # Plot Portfolio vs HODL
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df['Portfolio_Value'], mode='lines', name='Portfolio Value (Strategy)', line=dict(color='purple')))
            fig.add_trace(go.Scatter(x=df.index, y=df['HODL_Value'], mode='lines', name='HODL Strategy', line=dict(color='orange', dash='dash')))
            fig.update_layout(title='Portfolio Value vs HODL Strategy', xaxis_title='Date', yaxis_title='Value')
            st.plotly_chart(fig)
            
            
            
            
            # Extract buy and sell signals for plotting
            buy_signals = df[df['Signal'] == 1]
            sell_signals = df[df['Signal'] == -1]
            
            # Plot buy/sell signals with Bollinger Bands or Moving Averages
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name='Close Price', line=dict(color='blue')))
            fig2.add_trace(go.Scatter(x=df.index, y=df['Short_MA'], mode='lines', name=f'{short_window}-Day MA', line=dict(color='green', dash='dash')))
            fig2.add_trace(go.Scatter(x=df.index, y=df['Long_MA'], mode='lines', name=f'{long_window}-Day MA', line=dict(color='red', dash='dash')))
            fig2.add_trace(go.Scatter(x=df.index, y=df['Upper_Band'], mode='lines', name='Upper Bollinger Band', line=dict(color='orange', dash='dash')))
            fig2.add_trace(go.Scatter(x=df.index, y=df['Lower_Band'], mode='lines', name='Lower Bollinger Band', line=dict(color='orange', dash='dash')))
            fig2.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['Close'], mode='markers', marker=dict(color='green', symbol='triangle-up'), name='Buy Signal'))
            fig2.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['Close'], mode='markers', marker=dict(color='red', symbol='triangle-down'), name='Sell Signal'))
            fig2.update_layout(title=f'{strategy_type} Strategy with Buy and Sell Signals', xaxis_title='Date', yaxis_title='Price')
            st.plotly_chart(fig2)
            
        
            st.subheader("Trade History")
            st.dataframe(trades)
            
            return {
                "Final Value": portfolio_value,
                "Total Return (%)": total_return_percent,
                "Sharpe Ratio": sharpe_ratio,
                "Max Drawdown (%)": max_drawdown * 100,
                "Annualized Return (%)": annualized_return * 100,
                "Total Trades": len(trade_profits),
                "Winning Trades": wins,
                "Losing Trades": losses,
                "Win/Loss Ratio": win_loss_ratio,
                "Average Profit per Trade (%)": avg_profit_per_trade * 100,
                
            
                }

        # Execute backtest function
        for stock_name in selected_stock_names:
            stock_symbol = stock_options[stock_name]
            stock_allocation_pct = allocation[stock_name]
            stock_initial_capital = (initial_capital * stock_allocation_pct) / 100
            stock_result = backtest(
                stock_symbol=stock_symbol,
                initial_capital=stock_initial_capital,
                start_date=start_date,
                end_date=end_date,
                investment_type=investment_type,
                strategy_type=strategy_type,
                transaction_cost=transaction_cost,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
            
                )
            portfolio_results[stock_name] = stock_result
            
                
        #calculating the final portfolio perform
        
        if sum(allocation.values()) == 100:
            final_portfolio_value = sum(
                result["Final Value"] for result in portfolio_results.values()
                )
            
            st.subheader("## Combined Portfolio Performance")
            st.markdown(f"Initial Capital: ${initial_capital:,.2f}")
            #st.markdown(f"Final Portfolio Value: ${final_portfolio_value:.2f}")
            if initial_capital<final_portfolio_value:
                st.markdown(f"**Final Portfolio Value:** <span style='color:green; font-size:20px; font-weight:bold;'>${final_portfolio_value:.2f}</span>", unsafe_allow_html=True)
                st.markdown(f"**Total Profit:** <span style='color:green; font-size:20px; font-weight:bold;'>${final_portfolio_value-initial_capital:.2f}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"**Final Portfolio Value:** <span style='color:red; font-size:20px; font-weight:bold;'>${final_portfolio_value:.2f}</span>", unsafe_allow_html=True)
                st.markdown(f"**Total Loss:** <span style='color:red; font-size:20px; font-weight:bold;'>${final_portfolio_value-initial_capital:.2f}</span>", unsafe_allow_html=True)
                
            total_return_pct = (final_portfolio_value - initial_capital) / initial_capital * 100
            if total_return_pct>0:
                st.markdown(f"**Total Return:** <span style='color:green; font-size:18px; font-weight:bold;'>{total_return_pct:.2f}%</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"**Total Return:** <span style='color:red; font-size:18px; font-weight:bold;'>{total_return_pct:.2f}%</span>", unsafe_allow_html=True)
                
            
            #st.write(f"Total Return: {total_return_pct:.2f}%")
        else:
            st.sidebar.error("Please ensure the total allocation is 100%.")
        
        # Additional Visualizations
        #st.write("### Performance Highlights")
        #st.bar_chart([result["Sharpe Ratio"] for result in portfolio_results.values()], use_container_width=True)
        
        sharpe_ratios = [result["Sharpe Ratio"] for result in portfolio_results.values()]
        stock_names = list(portfolio_results.keys())
        fig = go.Figure([go.Bar(x=stock_names, y=sharpe_ratios, marker_color='lightblue')])
        fig.update_layout(title="Sharpe Ratio by Stock", xaxis_title="Stock", yaxis_title="Sharpe Ratio", template="plotly_dark")
        st.plotly_chart(fig)
        
        time_points = list(range(1, len(selected_stock_names) + 1))
        portfolio_values = [result["Final Value"] for result in portfolio_results.values()]
        fig2 = go.Figure([go.Scatter(x=time_points, y=portfolio_values, mode='lines+markers', marker=dict(color="cyan"))])
        fig2.update_layout(title="Portfolio Value Over Time", xaxis_title="Time (Simulation)", yaxis_title="Portfolio Value", template="plotly_dark")
        st.plotly_chart(fig2)
        
        #st.write("### Portfolio Value Over Time")
        #st.line_chart([result["Final Value"] for result in portfolio_results.values()], use_container_width=True)

        # Displaying Trade History Summary as well
        st.write("### Trade History Summary")
        for stock, result in portfolio_results.items():
            st.markdown(f"<p style='font-weight:bold; color:#1E90FF;'>{stock} Trades:</p>", unsafe_allow_html=True)
            st.write(f"**Total Trades:** {result['Total Trades']}")
            st.write(f"**Winning Trades:** {result['Winning Trades']}")
            st.write(f"**Losing Trades:** {result['Losing Trades']}")
        
        
        
        
        
        ###st.markdown("### Portfolio Performance Summary")
        ###if portfolio_results:
           ### total_portfolio_value = sum(result["Final Value"] for result in portfolio_results.values())
         ###   st.write(f"Total Portfolio Value: {total_portfolio_value:.2f}")
          ###  for stock, result in portfolio_results.items():
          ###      st.write(f"**{stock} Summary:**")
         ###   for key, value in result.items():
         ###       st.write(f"{key}: {value}") 
    
        
        
            
    
