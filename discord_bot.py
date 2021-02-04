import discord
import alpaca_trade_api as tradeapi
import pickle #TODO: use sqlite or sth instead of pickle
import os
import sqlite3 # for looking up database tickers

# set up db connection
conn = sqlite3.connect('assets.db')

# set up discord api
client = discord.Client()

with open('.discord_token', 'r') as f:
    DISCORD_TOKEN = f.read()

# set up alpaca api
with open('.alpaca_key_id','r') as f:
    KEY_ID = f.read()
with open('.alpaca_secret_key','r') as f:
    SECRET_KEY = f.read()
ENDPOINT = 'https://paper-api.alpaca.markets'

api = tradeapi.REST(KEY_ID, SECRET_KEY, ENDPOINT)
account = api.get_account()
api.list_positions()

DOCS = """
```
!buy [ticker] [amount]      | order 'amount' shares of 'ticker'
!sell [ticker] [amount]     | sell 'amount' shares of 'ticker'
!portfolio                  | list current portfolio
!open                       | list open orders
!cancel [ticker] [amount]   | cancel an open order
!search [name]              | find the ticker for a given company
!help                       | display this message
```
"""

# popoulate our assets database
def fetch_assets():
    assets = api.list_assets()
    print('len assets: ', len(assets))
    records = [(i.symbol, i.name) for i in assets]

    c = conn.cursor()
    # for stock in assets:
    #     c.execute(f'INSERT INTO tickers  (ticker, name) VALUES ({stock.symbol}, {stock.name});')
    c.executemany('insert into tickers (ticker,name) values (?,?)', records)
    conn.commit()

@client.event
async def on_ready():
    print(f'Logged on as {client.user}')

def is_valid_ticker(s):
    # c = conn.cursor()
    # rows = c.execute('SELECT ticker FROM tickers WHERE ticker = (?)', (s,))

    # return len(rows) >= 1
    # Above yields an error, as we can't do a len() of rows
    return True

open_orders_list = []

@client.event
async def on_message(message):
    # don't respond to our own messages
    if message.author == client.user:
        return

    if message.content.startswith('!sd'):
        await message.channel.send('Shutting down...')
        print('Shutting down...')
        await client.close()
        # also shut down sqlite connection
        conn.close()
        print('Client closed!')

    if message.content.startswith('!buy'):
        args = message.content.split(' ')[1:]
        ticker = args[0]
        shares = int(args[1])
        if not is_valid_ticker(ticker):
            await message.channel.send(f'Invalid ticker {ticker}')
            return

        # place the buy order
        # TODO: add checks for portfolio value, so we don't send impossible requests
        # TODO: eventually keep a database of users so no individual spends too much
        api.submit_order(
            symbol=ticker,
            qty=shares,
            side='buy',
            type='market',
            time_in_force='gtc'
        )

        await message.channel.send(f'Order for {shares} shares of {ticker} submitted.')

    if message.content.startswith('!sell'):
        args = message.content.split(' ')[1:]
        ticker = args[0]
        shares = int(args[1])
        if not is_valid_ticker(ticker):
            await message.channel.send(f'Invalid ticker {ticker}')
            return

        # place the buy order
        # TODO: add checks for portfolio value, so we don't send impossible requests
        # TODO: eventually keep a database of users so no individual spends too much
        api.submit_order(
            symbol=ticker,
            qty=shares,
            side='sell',
            type='market',
            time_in_force='gtc'
        )

        await message.channel.send(f'Order to sell {shares} shares of {ticker} submitted.')
               
        
    if message.content.startswith('!portfolio'):
        positions = api.list_positions()
        # TODO: include cash value of acct
        lines = [f'{pos.qty} shares of {pos.symbol:<8}{" ":>10}${pos.market_value}' for pos in positions]
        # make our message monospace
        msg = '\n'.join(lines)
        msg = '```\n' + msg + '```\n'
        await message.channel.send(msg)

    if message.content.startswith('!cancel'):
        args = message.content.split(' ')[1:]
        ticker = args[0]
        shares = args[1]
        open_orders = api.list_orders(status='open',limit=100,nested=True)
        order_ids= [i.id for i in open_orders if i.symbol == ticker and i.qty == shares]
        if len(order_ids) > 0:
            order_id = order_ids[0]
            api.cancel_order(order_id)
        else:
            message.channel.send(f'No matching order for {shares} shares of {ticker}. Check !open')

    # list open orders
    if message.content.startswith('!open'):
        open_orders = api.list_orders(
            status='open',
            limit=100,
            nested=True
        )
        response_str = ''
        for order in open_orders:
            response_str += f'Order for {order.qty} shares of {order.symbol}\n'

        await message.channel.send(response_str)
    
    # get the most recent quote on a ticker
    if message.content.startswith('!price'):
        args = message.content.split(' ')[1:]
        ticker = args[0]
        if not is_valid_ticker(ticker):
            await message.channel.send(f'Ticker {ticker} is not recognized. Consider using !search')
            return
        trade = api.get_last_trade(ticker)
        await message.channel.send(f'Most recent price for {ticker} is ${trade.price:.2f}')

    if message.content.startswith('!help'):
        await message.channel.send(DOCS)

    # TODO: either error for *very* long searches (discord won't accept past a certain length)
    #       or figure out how to divide it up into multiple messages
    if message.content.startswith('!search'):
        # remove our command, just take the rest of the string 
        company_name = ' '.join(message.content.split(' ')[1:])
        c = conn.cursor()

        t = (company_name,)
        c.execute("SELECT name, ticker FROM tickers WHERE NAME LIKE ?", ('%'+company_name+'%',))
        rows = c.fetchall()
        msg = ''
        for row in rows:
            name, ticker = row
            msg += f'{ticker:<15}{name:<70}\n'
        await message.channel.send(msg)


    # TODO: add permission check for internal update functions
    if message.content.startswith('!_update_asset_db'):
        print('updating asset database')
        fetch_assets()
    
client.run(DISCORD_TOKEN)