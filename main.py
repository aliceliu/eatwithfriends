#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
FACEBOOK_APP_ID = '232787613548493'
FACEBOOK_APP_SECRET = 'fcc45d1a7b8a9867516119a6ceb40648'

import facebook
import webapp2
import jinja2
import os
import logging

from google.appengine.ext import db
from webapp2_extras import sessions

config = {}
config['webapp2_extras.sessions'] = dict(secret_key='')

jinja_environment = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

class User(db.Model):
	id = db.StringProperty(required=True)
	created = db.DateTimeProperty(auto_now_add=True)
	updated = db.DateTimeProperty(auto_now=True)
	name = db.StringProperty(required=True)
	profile_url = db.StringProperty(required=True)
	access_token = db.StringProperty(required=True)
	meal = db.StringProperty()

class BaseHandler(webapp2.RequestHandler):
	"""Provides access to the active Facebook user in self.current_user

	The property is lazy-loaded on first access, using the cookie saved
	by the Facebook JavaScript SDK to determine the user ID of the active
	user. See http://developers.facebook.com/docs/authentication/ for
	more information.
	"""
	@property
	def current_user(self):
		if self.session.get("user"):
			# User is logged in
			return self.session.get("user")
		else:
			# Either used just logged in or just saw the first page
			# We'll see here
			cookie = facebook.get_user_from_cookie(self.request.cookies,
												   FACEBOOK_APP_ID,
												   FACEBOOK_APP_SECRET)
			if cookie:
				# Okay so user logged in.
				# Now, check to see if existing user
				user = User.get_by_key_name(cookie["uid"])
				if not user:
					# Not an existing user so get user info
					graph = facebook.GraphAPI(cookie["access_token"])
					profile = graph.get_object("me")
					user = User(
						key_name=str(profile["id"]),
						id=str(profile["id"]),
						name=profile["name"],
						profile_url=profile["link"],
						access_token=cookie["access_token"]
					)
					user.put()
				elif user.access_token != cookie["access_token"]:
					user.access_token = cookie["access_token"]
					user.put()
				# User is now logged in
				self.session["user"] = dict(
					name=user.name,
					profile_url=user.profile_url,
					id=user.id,
					access_token=user.access_token,
				)
				return self.session.get("user")
		return None

	def dispatch(self):
		"""
		This snippet of code is taken from the webapp2 framework documentation.
		See more at
		http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html

		"""
		self.session_store = sessions.get_store(request=self.request)
		try:
			webapp2.RequestHandler.dispatch(self)
		finally:
			self.session_store.save_sessions(self.response)

	@webapp2.cached_property
	def session(self):
		"""
		This snippet of code is taken from the webapp2 framework documentation.
		See more at
		http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html

		"""
		return self.session_store.get_session()


class MainHandler(BaseHandler):
	def get(self):
		template_values = {'facebook_app_id':FACEBOOK_APP_ID,
						   'current_user':self.current_user,
						   }
		template = jinja_environment.get_template("home.html")
		self.response.out.write(template.render(template_values))

class LogoutHandler(BaseHandler):
	def get(self):
		if self.current_user is not None:
			user = db.get(db.Key.from_path("User",self.current_user["id"]))
			user.meal = None
			user.put()
			self.session['user'] = None
		self.redirect('/')

class ResultHandler(BaseHandler):
	def get(self):
		meal = self.request.get("meal")
		result = []
		user = db.get(db.Key.from_path("User",self.current_user["id"]))

		show_self = self.request.get("choice")
		if show_self:
			user.meal = meal
			user.put()

		graph = facebook.GraphAPI(user.access_token)
		friends = graph.get_connections("me", "friends")["data"]
		logging.info(friends)
		
		for friend in friends:
			f = db.get(db.Key.from_path("User", friend["id"]))
			if f and (f.meal == meal):
				result.append(f)
		
		template_values = {'facebook_app_id':FACEBOOK_APP_ID,
						   'current_user':self.current_user,
						   'meal':meal,
						   'result':result}
		template = jinja_environment.get_template("result.html")
		self.response.out.write(template.render(template_values))
		
		
app = webapp2.WSGIApplication([
	('/', MainHandler),
	('/logout', LogoutHandler),
	('/result', ResultHandler)

], debug=True, config=config)

