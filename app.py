from dotenv import load_dotenv
import os

from millify import millify
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd
import numpy as np
import requests

oad_dotenv()
PAGE_CONFIG = {"page_title":"Spendings Report","page_icon":":dollar:","layout":"centered"}
st.set_page_config(**PAGE_CONFIG)

def getdata():
	DATABASE_ID = os.environ.get('database_id')
	NOTION_URL = os.environ.get('notion_url')
	class NotionSync:
			def __init__(self):
					pass    
			def query_databases(self,integration_token=os.environ.get('integration_token'),notion_version=os.environ.get('notion_version')):
					database_url = NOTION_URL + DATABASE_ID + "/query"
					response = requests.post(database_url, headers={"Authorization": f"{integration_token}","Notion-Version":f"{notion_version}"})
					if response.status_code != 200:
							raise Exception(f'Response Status: {response.status_code} {response.text}')
					else:
							data = [response.json()]
							while response.json()['has_more']:
								cur = response.json()['next_cursor']
								response = requests.post(database_url, json={'start_cursor':cur}, headers={"Authorization": f"{integration_token}","Notion-Version":f"{notion_version}"})
								# print(response.json())
								data.append(response.json())
							return data
			def get_projects_titles(self,data_json):
					return list(data_json["results"][0]["properties"].keys())
			def get_projects_data(self,data_json,projects):
					data = []
					for i in data_json:
						res = i["results"]
						for val in res:
							row = []
							el = val['properties']
							for p in projects:
								tipe = el[p]['type']
								# print(tipe)
								# pprint.PrettyPrinter(indent=4).pprint(el[p][tipe])
								if tipe == 'formula':
									key = el[p][tipe]['type']
									if key == 'date':
										row.append(el[p][tipe][key]['start'])
									else:
										row.append(el[p][tipe][key])
								elif tipe =='title':
									row.append(el[p][tipe][0]['plain_text'])
								elif tipe =='select':
									# print(el[p][tipe])
									row.append(el[p][tipe]['name'])
								elif tipe == 'rich_text':
									# print(el[p][tipe])
									row.append(el[p][tipe][0]['text']['content'])
								else:
									row.append(el[p][tipe])
							data.append(row)
					return data
	nsync = NotionSync()
	data = nsync.query_databases()
	projects = nsync.get_projects_titles(data[0])
	data = nsync.get_projects_data(data,projects)
	money_df = pd.DataFrame(data, columns = projects)
	return money_df

def main():
	money_df = getdata()
	money_df['Date'] = pd.to_datetime(money_df['Date'],format='%Y-%m-%dT%H:%M:%S.%f%z')
	st.title("My Spendings Report")
	menu = ["Monthly Spendings","All Time Spendings"]
	choice = st.selectbox('Menu',menu)
 	
	#All time report
	if choice == menu[1]:
		st.header("All Time Spendings")
		most_spend_cat = money_df[money_df['method']=='cash'].groupby('Category').sum().sort_values('price',ascending=False).iloc[0]

		st.subheader('Metrics')
		col1 = st.columns(2)
		col1[0].metric(label='Total Spendings',
							value=millify(money_df[money_df['method']=='cash']['price'].sum(), precision=2))
		col1[1].metric(label='Highest Spending Category',
							value=most_spend_cat.name.capitalize(),
							delta=millify(most_spend_cat.price, precision=2),
							delta_color='off')

		st.subheader('Spendings per Category')
		fig = px.bar(money_df[money_df['method']=='cash'].groupby('Category')['price'].sum().reset_index(),
								x='Category',y='price',text_auto=True,
								labels={'price':'Total Spendings'})
		fig.update_layout(xaxis={'categoryorder':'total ascending'})
		st.plotly_chart(fig, use_container_width=True)

		st.subheader('Spendings per Method')
		fig = px.bar(money_df.groupby('method')['price'].sum().reset_index(),
								x='method',y='price',text_auto=True,
								labels={'price':'Total Spendings'})
		fig.update_layout(xaxis={'categoryorder':'total ascending'})
		st.plotly_chart(fig, use_container_width=True)

		st.subheader('Spending Trends')
		fig = px.line(money_df[money_df['method']=='cash'].groupby(pd.Grouper(key='Date',freq='M'))['price'].sum().reset_index(), 
								x="Date", y="price", 
								labels={'price':'Total Spendings'})
		st.plotly_chart(fig, use_container_width=True)
	#Monthly Report
	elif choice == menu[0]:
		curr = pd.Timestamp.now()
		last_month = curr.replace(day=1) - pd.Timedelta(days=1)
		df = money_df.loc[money_df['Date'].dt.to_period(freq='M')== curr.to_period(freq='M') ].reset_index()
		last_month_df =  money_df.loc[money_df['Date'].dt.to_period(freq='M')== last_month.to_period(freq='M') ].reset_index()
		most_spend_cat = df[df['method']=='cash'].groupby('Category').sum().sort_values('price',ascending=False).iloc[0]

		st.header(f"Monthly Spendings {curr.strftime('%b %Y')}")

		st.subheader('Metrics')
		col1 = st.columns([1,1,2])
		col1[0].metric(label='This Month Spendings',
							value=millify(df[df['method']=='cash']['price'].sum(), precision=2),
							delta=f"{(df[df['method']=='cash']['price'].sum()-last_month_df[last_month_df['method']=='cash']['price'].sum())/last_month_df[last_month_df['method']=='cash']['price'].sum()*100:.2f}%",
							delta_color='inverse')
		col1[1].metric(label='Last Month Spendings',
							value=millify(last_month_df[last_month_df['method']=='cash']['price'].sum(), precision=2))
		col1[2].metric(label='Highest Spending Category',
							value=most_spend_cat.name.capitalize(),
							delta=millify(most_spend_cat.price, precision=2),
							delta_color='off')
		
		st.subheader('Spendings per Category')
		fig = px.bar(df[df['method']=='cash'].groupby('Category')['price'].sum().reset_index(),
								x='Category',y='price',text_auto=True,
								labels={'price':'Total Spendings'})
		fig.update_layout(xaxis={'categoryorder':'total ascending'})
		st.plotly_chart(fig, use_container_width=True)

		st.subheader('Spending Trends')
		fig = px.line(df[df['method']=='cash'].groupby(pd.Grouper(key='Date',freq=('D')))['price'].sum().reset_index().sort_values('Date'), 
								x="Date", y="price", 
								labels={'price':'Total Spendings'})
		st.plotly_chart(fig, use_container_width=True)
		#st.dataframe(df[['Name','price','method','Category','Date']])
	
if __name__ == '__main__':
	main()