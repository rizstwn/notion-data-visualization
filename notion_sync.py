from __future__ import annotations
from typing import Union

import requests


class NotionSyncDB:
	def __init__(self,database_id: str, integration_token: str, notion_version: str, notion_url: str) -> None:
		self.token = integration_token
		self.version = notion_version
		self.database_id = database_id
		self.notion_url = notion_url
		self.properties = self.get_database_properties()

	def get_database_properties(self) -> Union[str,dict]:
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

	def query_database(self, query_filter: dict,query_sort: list[dict]) -> list[dict]:
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
		return data

	def process_db_data(self,row:dict) -> dict:
		properties = self.properties.keys()
		res_data = {}
		row = row['properties']
		for prop in properties:
			try:
				prop_val = row[prop]
				prop_type = prop_val['type']
				if prop_type in ['number', 'created_time', 'last_edited_time']:
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
				elif prop_type == 'unique_id':
					temp_data = prop_val['unique_id']
					if 'prefix' in temp_data.keys():
						temp_data = f"{temp_data['prefix']}-{temp_data['number']}"
					else:
						temp_data = temp_data['number']
				else:
					raise Exception(f'Properties Type not found: {prop}')
				res_data[prop] = temp_data
			except Exception as e:
				print(e,row)
		return res_data
