import os
import json
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from millify import millify
from dotenv import load_dotenv

load_dotenv()
PAGE_CONFIG = {"page_title":"Spendings Report","page_icon":":dollar:","layout":"centered"}
st.set_page_config(**PAGE_CONFIG)

def getdata():
	DATABASE_ID = os.environ.get('DATABASE_ID')
	NOTION_URL = os.environ.get('NOTION_URL')
	INTEGRATION_TOKEN = os.environ.get('INTEGRATION_TOKEN')
	NOTION_VERSION = os.environ.get('NOTION_VERSION')

	filters = {}
	sorts = [{
			"property": "Date Payment",
			"direction": "ascending"
		}
	]

	class NotionSyncDB:
		def __init__(self,database_id, integration_token, notion_version, notion_url):
			self.token = integration_token
			self.version = notion_version
			self.database_id = database_id
			self.notion_url = notion_url
			self.properties = self.get_database_properties()

		def get_database_properties(self):
			header = {
				"Authorization": f"Bearer {self.token}",
				"Notion-Version":self.version
			}
			db_url = f"{self.notion_url}{self.database_id}"
			response = requests.get(db_url, headers=header)
			if response.status_code != 200:
				raise Exception(f'Response Status: {response.status_code} {response.text}')
			else:
				return response.json()['properties']

		def query_database(self, query_filter,query_sort, stored_data=None):
			query_url = f"{self.notion_url}{self.database_id}/query"
			params = {
				"sorts":query_sort,
			}
			header = {
				"Authorization": f"Bearer {self.token}", 
				"Content-Type": "application/json", 
				"Notion-Version":self.version
			}
			if query_filter:
				params['filter'] = query_filter
			
			response = requests.post(query_url, headers=header, json=params)
			if response.status_code != 200:
				raise Exception(f'Response Status: {response.status_code} {response.text}')
			else:
				json_data = response.json()
				data = [self.process_db_data(x) for x in json_data['results']]
				while json_data['has_more']:
					cur = json_data['next_cursor']
					params['start_cursor'] = cur
					response = requests.post(query_url, headers=header, json=params)
					json_data = response.json()
					processed_data = [self.process_db_data(x) for x in json_data['results']]
					data += processed_data
			if stored_data:
				data = stored_data + data
			with open("expense_data.json",'w') as f:
				f.write(json.dumps(data))
			return data

		def process_db_data(self,row):
			properties = self.properties.keys()
			res_data = {}
			row = row['properties']
			for prop in properties:
				try:
					prop_val = row[prop]
					prop_type = prop_val['type']
					if prop_type in ['number', 'created_time']:
						temp_data = prop_val[prop_type]
					elif prop_type in ['rich_text','title']:
						temp_data = " ".join([text['plain_text'] for text in prop_val[prop_type]])
					elif prop_type == 'select':
						temp_data = prop_val['select']['name']
					elif prop_type == 'formula':
						formula_type = prop_val['formula']['type']
						if formula_type in ['number','string']:
							temp_data = prop_val['formula'][formula_type]
						elif formula_type in ['date']:
							temp_data = prop_val['formula'][formula_type]['start']
					else:
						raise Exception(f'Properties Type not found: {prop}')
					res_data[prop] = temp_data
				except Exception as e:
					print(e,row)
			return res_data

	expense_db = NotionSyncDB(database_id=DATABASE_ID, integration_token=INTEGRATION_TOKEN, 
							notion_version=NOTION_VERSION, notion_url=NOTION_URL)
	stored_data=None
	if os.path.isfile("expense_data.json"):
		with open("expense_data.json",'r') as f:
			stored_data = json.load(f)
	latest_date = stored_data[-1]['Created At']
	filters = {
		"property": "Created At",
		"date": {
		"after": latest_date
		}
	}
	data = expense_db.query_database(query_filter=filters,query_sort=sorts,stored_data=stored_data)
	money_df = pd.DataFrame(data, columns = expense_db.properties.keys())
	return money_df

def main():
	money_df = getdata()
	money_df['Date Payment'] = pd.to_datetime(money_df['Date Payment'],format='%Y-%m-%dT%H:%M:%S.%f%z')
	st.title("My Spendings Report")
	menu = ["Monthly Spendings","All Time Spendings"]
	choice = st.selectbox('Menu',menu)

	#All time report
	if choice == menu[1]:
		st.header("All Time Spendings")
		most_spend_cat = money_df[money_df['Payment']=='cash'][['Category','Price in Number']].groupby('Category').sum().sort_values('Price in Number',ascending=False).iloc[0]

		st.subheader('Metrics')
		col1 = st.columns(2)
		col1[0].metric(label='Total Spendings',
							value=millify(money_df[money_df['Payment']=='cash']['Price in Number'].sum(), precision=2))
		col1[1].metric(label='Highest Spending Category',
							value=most_spend_cat.name.capitalize(),
							delta=millify(most_spend_cat['Price in Number'], precision=2),
							delta_color='off')

		st.subheader('Spendings per Category')
		fig = px.bar(money_df[money_df['Payment']=='cash'].groupby('Category')['Price in Number'].sum().reset_index(),
								x='Category',y='Price in Number',text_auto=True,
								labels={'Price in Number':'Total Spendings'})
		fig.update_layout(xaxis={'categoryorder':'total ascending'})
		st.plotly_chart(fig, use_container_width=True)

		st.subheader('Spendings per Method')
		fig = px.bar(money_df.groupby('Payment')['Price in Number'].sum().reset_index(),
								x='Payment',y='Price in Number',text_auto=True,
								labels={'Price in Number':'Total Spendings'})
		fig.update_layout(xaxis={'categoryorder':'total ascending'})
		st.plotly_chart(fig, use_container_width=True)

		st.subheader('Spending Trends')
		fig = px.line(money_df[money_df['Payment']=='cash'].groupby(pd.Grouper(key='Date Payment',freq='M'))['Price in Number'].sum().reset_index(), 
								x="Date Payment", y="Price in Number", 
								labels={'Price in Number':'Total Spendings'})
		st.plotly_chart(fig, use_container_width=True)
	#Monthly Report
	elif choice == menu[0]:
		curr = pd.Timestamp.now()
		last_month = curr.replace(day=1) - pd.Timedelta(days=1)
		df = money_df.loc[money_df['Date Payment'].dt.to_period(freq='M')== curr.to_period(freq='M') ].reset_index()
		last_month_df =  money_df.loc[money_df['Date Payment'].dt.to_period(freq='M')== last_month.to_period(freq='M') ].reset_index()
		most_spend_cat = df[df['Payment']=='cash'][['Category','Price in Number']].groupby('Category').sum().sort_values('Price in Number',ascending=False).iloc[0]

		st.header(f"Monthly Spendings {curr.strftime('%b %Y')}")

		st.subheader('Metrics')
		col1 = st.columns([1,1,2])
		col1[0].metric(label='This Month Spendings',
							value=millify(df[df['Payment']=='cash']['Price in Number'].sum(), precision=2),
							delta=f"{(df[df['Payment']=='cash']['Price in Number'].sum()-last_month_df[last_month_df['Payment']=='cash']['Price in Number'].sum())/last_month_df[last_month_df['Payment']=='cash']['Price in Number'].sum()*100:.2f}%",
							delta_color='inverse')
		col1[1].metric(label='Last Month Spendings',
							value=millify(last_month_df[last_month_df['Payment']=='cash']['Price in Number'].sum(), precision=2))
		col1[2].metric(label='Highest Spending Category',
							value=most_spend_cat.name.capitalize(),
							delta=millify(most_spend_cat['Price in Number'], precision=2),
							delta_color='off')
		
		st.subheader('Spendings per Category')
		fig = px.bar(df[df['Payment']=='cash'].groupby('Category')['Price in Number'].sum().reset_index(),
								x='Category',y='Price in Number',text_auto=True,
								labels={'Price in Number':'Total Spendings'})
		fig.update_layout(xaxis={'categoryorder':'total ascending'})
		st.plotly_chart(fig, use_container_width=True)

		st.subheader('Spending Trends')
		fig = px.line(df[df['Payment']=='cash'].groupby(pd.Grouper(key='Date Payment',freq=('D')))['Price in Number'].sum().reset_index().sort_values('Date Payment'), 
								x="Date Payment", y="Price in Number", 
								labels={'Price in Number':'Total Spendings'})
		st.plotly_chart(fig, use_container_width=True)
		#st.dataframe(df[['Name','price','Payment','Category','Date Payment']])
	
if __name__ == '__main__':
	main()