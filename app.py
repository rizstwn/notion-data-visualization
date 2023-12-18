from __future__ import annotations

import os
import json
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from millify import millify
from dotenv import load_dotenv
from notion_sync import NotionSyncDB

load_dotenv()
PAGE_CONFIG = {"page_title":"Spendings Report","page_icon":":dollar:","layout":"centered"}
st.set_page_config(**PAGE_CONFIG)

def get_data() -> pd.DataFrame:
	DATABASE_ID = os.environ.get('DATABASE_ID')
	NOTION_URL = os.environ.get('NOTION_URL')
	INTEGRATION_TOKEN = os.environ.get('INTEGRATION_TOKEN')
	NOTION_VERSION = os.environ.get('NOTION_VERSION')

	filters = {}
	sorts = [{
			"property": "Updated At",
			"direction": "ascending"
		}
	]

	expense_db = NotionSyncDB(database_id=DATABASE_ID, 
				integration_token=INTEGRATION_TOKEN, 
				notion_version=NOTION_VERSION, 
				notion_url=NOTION_URL)

	#If previous data already exist
	filename = "moneybook_data.json"
	if os.path.isfile(filename):
		with open(filename,'r') as f:
			stored_data = json.load(f)
		latest_date = list(stored_data['Updated At'].values())[-1]
		filters = {
			"property": "Updated At",
			"date": {
			"after": latest_date
			}
		}
		stored_data = pd.DataFrame(stored_data)
		data = expense_db.query_database(query_filter=filters,query_sort=sorts)
		data = update_existing_data(stored_data,data)
	else:
		data = expense_db.query_database(query_filter=filters,query_sort=sorts)
		data = pd.DataFrame(data, columns = expense_db.properties.keys())
	
	with open(filename,'w') as f:
		f.write(data.to_json())
	return data

def update_existing_data(old_df:pd.DataFrame, new_data:list[dict]) -> pd.DataFrame:
	temp_new_df = []
	for row in new_data:
		row_id = row['ID']
		if row_id in old_df['ID']:
			old_df.loc[old_df['ID']==row_id] = row.values()
		else:
			temp_new_df.append(row)
	temp_new_df = pd.DataFrame(temp_new_df)
	df = pd.concat(old_df,temp_new_df)
	return df

def get_diff(val1:int, val2:int, percentage:bool =True) -> float:
	res = val1-val2
	if percentage:
		res = res/val2*100
	return res

def main():
	money_df = get_data()
	money_df['Date Payment'] = pd.to_datetime(money_df['Date Payment'],format='%Y-%m-%dT%H:%M:%S.%f%z')
	st.title("My Spendings Report")
	menu = ["Monthly Spendings","All Time Spendings"]
	choice = st.selectbox('Menu',menu)

	st.dataframe(money_df)

	#Monthly Report
	if choice == menu[0]:
		curr = pd.Timestamp.now()
		last_month = curr.replace(day=1) - pd.Timedelta(days=1) #Last day of previous month
		df = money_df.loc[money_df['Date Payment'].dt.to_period(freq='M')== curr.to_period(freq='M') ].reset_index(drop=True)
		last_month_df =  money_df.loc[money_df['Date Payment'].dt.to_period(freq='M')== last_month.to_period(freq='M') ].reset_index(drop=True)
		most_spend_cat = df[df['Category']!='emoney'][['Category','Amount']]\
			.groupby('Category')\
			.sum()\
			.sort_values('Amount',ascending=False).iloc[0] #E-money doesn't count as spendings

		st.header(f"Monthly Report for {curr.strftime('%b %Y')}")

		st.subheader('Metrics')
		col1 = st.columns([1,1,2])
		last_month_total = last_month_df[last_month_df['Category']!='emoney']['Amount'].sum()
		curr_month_total = df[df['Category']!='emoney']['Amount'].sum()
		month_diff = get_diff(curr_month_total, last_month_total)
		col1[0].metric(label='This Month Spendings',
							value=millify(curr_month_total, precision=2),
							delta=f"{month_diff:.2f}%",
							delta_color='inverse')
		col1[1].metric(label='Last Month Spendings',
							value=millify(last_month_total, precision=2))
		col1[2].metric(label='Highest Spending Category',
							value=most_spend_cat.name.capitalize(),
							delta=millify(most_spend_cat['Amount'], precision=2),
							delta_color='off')
		
		st.subheader('Spendings per Group')
		fig = px.pie(df[df['Payment']=='cash'].groupby('Category')['Amount'].sum().reset_index(),
						names='Category',values='Amount',title="Category",
						labels={'Amount':'Total Spendings'})
		st.plotly_chart(fig, use_container_width=True)
		col2 = st.columns([1,1])
		fig = px.pie(df[df['Category']=='emoney'].groupby('Name')['Amount'].sum().reset_index(),
						names='Name',values='Amount',title="Emoney Topup",
						labels={'Amount':'Total Spendings'})
		col2[0].plotly_chart(fig, use_container_width=True)
		fig = px.pie(df.groupby('Payment')['Amount'].sum().reset_index(),
						names='Payment',values='Amount',title="Payment",
						labels={'Amount':'Total Spendings'})
		col2[1].plotly_chart(fig, use_container_width=True)

		st.subheader('Spending Comparison')
		combine_df = pd.concat([df,last_month_df])
		fig = px.bar(combine_df.groupby(['Month Year Date','Category'])['Amount'].sum().reset_index(),
						x='Category',y='Amount',color='Month Year Date',barmode='group',
						labels={'Amount':'Total Spendings'})
		st.plotly_chart(fig, use_container_width=True)

		st.subheader('Spending Trends')
		fig = px.area(df[df['Payment']=='cash'].groupby(pd.Grouper(key='Date Payment',freq=('D')))['Amount'].sum().reset_index().sort_values('Date Payment'), 
								x="Date Payment", y="Amount", 
								labels={'Amount':'Total Spendings'})
		st.plotly_chart(fig, use_container_width=True)

	#All time report
	elif choice == menu[1]:
		st.header("All Time Spendings")
		most_spend_cat = money_df[money_df['Payment']=='cash'][['Category','Amount']].groupby('Category').sum().sort_values('Amount',ascending=False).iloc[0]

		st.subheader('Metrics')
		col1 = st.columns(2)
		col1[0].metric(label='Total Spendings',
							value=millify(money_df[money_df['Payment']=='cash']['Amount'].sum(), precision=2))
		col1[1].metric(label='Highest Spending Category',
							value=most_spend_cat.name.capitalize(),
							delta=millify(most_spend_cat['Amount'], precision=2),
							delta_color='off')
		
		st.subheader('Spending Trends')
		fig = px.area(money_df[money_df['Payment']=='cash'].groupby(pd.Grouper(key='Date Payment',freq='M'))['Amount'].sum().reset_index(), 
								x="Date Payment", y="Amount", 
								labels={'Amount':'Total Spendings'})
		st.plotly_chart(fig, use_container_width=True)
		
		st.subheader('Spendings per Category')
		fig = px.bar(money_df[money_df['Payment']=='cash'].groupby('Category')['Amount'].sum().reset_index(),
								x='Category',y='Amount',text_auto=True,
								labels={'Amount':'Total Spendings'})
		fig.update_layout(xaxis={'categoryorder':'total ascending'})
		st.plotly_chart(fig, use_container_width=True)

		st.subheader('Spendings per Method')
		fig = px.bar(money_df.groupby('Payment')['Amount'].sum().reset_index(),
								x='Payment',y='Amount',text_auto=True,
								labels={'Amount':'Total Spendings'})
		fig.update_layout(xaxis={'categoryorder':'total ascending'})
		st.plotly_chart(fig, use_container_width=True)
	
if __name__ == '__main__':
	main()