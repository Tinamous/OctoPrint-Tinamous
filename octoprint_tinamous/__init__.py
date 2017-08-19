# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.util import RepeatedTimer

import octoprint.plugin

import logging
import octoprint.plugin
import os
import json
import requests

# Publish events to Tinmaous and provide a simple UI to show values from certain devices
# e.g. humidity levels for humidity controlled filament storage.
class TinamousPlugin(octoprint.plugin.StartupPlugin,
					octoprint.plugin.SettingsPlugin,
                    octoprint.plugin.AssetPlugin,
                    octoprint.plugin.TemplatePlugin,
					octoprint.plugin.SimpleApiPlugin,
					octoprint.plugin.EventHandlerPlugin):

	def __init__(self):
		self._timer = None
		self._auto_post_interval_minutes = 10;

	def on_after_startup(self):
		self._logger.info("Tinamous Printing Plugin on_after_startup")
		#snapshotUrl = self._settings.globalGet(["webcam", "snapshot"])
		if self._settings.get(["enabled"]):
			self.start_timers()

	#def initialize(self):
		#self._logger.setLevel(logging.DEBUG)

	def start_timers(self, ):
		if self._settings.get(["auto_post_measurements", "enabled"]):
			measurements_interval = self._settings.get(["auto_post_measurements", "interval_minutes"]) * 60.0
			self._measurements_timer = RepeatedTimer(measurements_interval, self.auto_post_measurement, None, None, True)
			self._measurements_timer.start()
			self._logger.info("Started auto-post measurements timer at {}s".format(measurements_interval))

		if self._settings.get(["auto_post_picture", "enabled"]):
			picture_interval = self._settings.get(["auto_post_picture", "interval_minutes"]) * 60.0
			self._picture_timer = RepeatedTimer(picture_interval, self.auto_post_picture, None, None, True)
			self._picture_timer.start()
			self._logger.info("Started auto-post picture timer at {}s".format(picture_interval))

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			enabled=True, # Isn't this just the same as disabling the plugin?
			# Measurements
			auto_post_measurements = dict (
				enabled = True,
				interval_minutes=1,
				during_printing_only = False,
			),
			# Status posts with a picture
			auto_post_picture = dict (
				enabled=True,
				# Automatically post a status message (picture) every n-minutes.
				interval_minutes=10,
				include_hashtag="#TodayOnTheUltimaker",
				# Tinamous allows for a unique media id so that multiple photos can be
				# assigned to the one id to allow a timeseries style view.
				media_unique_id="",
			),
			tinamous_settings=dict (
				# Your Tinamous.com account name (e.g. Demo.Timamous.com -> Accountname is Demo).
				account_name="",
				# The device logon this should use.
				username="",
				password=""
			),
			print_events=dict (
				# Custom OctoPrint event from the Who's Printing plougin.
				WhosPrinting=dict(
					Message="Ohhh Hello... {username} is printing!",
					Enabled=True,
					IncludePicture=True,
				),
				# Standard OctoPrint events
				PrintStarted=dict(
					Message="Yay, a new print has started! Filename: {filename}",
					Enabled=True,
					IncludePicture=True,
				),
				PrintFailed=dict(
					Message="Oh no! The print has failed :-(. Reason: {reason}",
					Enabled=True,
					IncludePicture=True,
				),
				PrintCancelled=dict(
					Message="Uh oh... the print was cancelled!",
					Enabled=True,
					IncludePicture=True,
				),
				PrintDone=dict(
					Message="Print finished successfully!",
					Enabled=True,
					IncludePicture=True,
				),
				PrintPaused=dict(
					Message="Printing has been paused...",
					Enabled=True,
					IncludePicture=True,
				),
				PrintResumed=dict(
					Message="Phew! Printing has been resumed! Back to work...",
					Enabled=True,
					IncludePicture=True,
				)
			)
		)

	def get_template_configs(self):
		return [
			dict(type="settings", custom_bindings=False),
		]

	##~~ AssetPlugin mixin

	def get_assets(self):
		return dict(
			js=["js/tinamous.js"],
		)

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
		return dict(
			tinamous=dict(
				displayName="Tinamous Publisher",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="Tinamous",
				repo="OctoPrint-Tinamous",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/Tinamous/OctoPrint-Tinamous/archive/{target_version}.zip"
			)
		)

	##~~ Events hook

	def on_event(self, event, payload):
		events = self._settings.get(['print_events'], merged=True)

		# Fired by the Pi Power Plug in when it has measured the power usage/temperature, light level etc.
		if event == "PiPowerMeasured":
			self.post_power_measurements(payload)
			return

		if event in events and events[event] and events[event]['Enabled']:

			## Get the event settings, message, enabled, etc.
			event_settings = self._settings.get(['print_events', event], merged=True)

			status_message = self.populate_status_message(event_settings, payload)

			message = {}
			# Message contains 'username' and 'filename' replacement tokens.
			message['Message'] = status_message
			message['Lite'] = True

			if (event_settings["IncludePicture"]):
				self._logger.warn("Not taking picture. TODO: Take and post picture!")
				# if posting a picture with the status message.
				# message['MediaIds'] = []

			self._logger.debug("Attempting post of Tinamous status message: {}".format(message))

			self.post_status_to_tinamous(message)
		else:
			self._logger.debug("Tinamous not configured for event: {0}".format(event))
			return

	def populate_status_message(self, event_settings, payload):
		username = "somebody"
		# username comes from the "Who's Printing" plugin.
		if "username" in payload and payload["username"]:
			# TODO: Lookup the user details from the user_manager.
			username = payload["username"]
		elif "name" in payload and payload["name"]:
			username = payload["name"]

		filename = "*Missing*"
		if "file" in payload and payload["name"]:
			# TODO: Lookup the user details from the user_manager.
			filename = payload["name"]

		elapsed_time = ""
		if "time" in payload and payload["time"]:
			import datetime
			import octoprint.util
			elapsed_time = octoprint.util.get_formatted_timedelta(datetime.timedelta(seconds=payload["time"]))

		# Reason is injected into the payload by the
		# print failed dialog box of Who's Printing.
		reason = ""
		if "reason" in payload and payload["reason"]:
			reason = payload["reason"]

		return event_settings['Message'].format(username=username, filename=filename, elapsedTime=elapsed_time, reason=reason)

	def post_status_to_tinamous(self, message):
		try:
			result = self.post_to_tinamous("api/v1/Status", message)
		except Exception, e:
			self._logger.exception("An error occurred connecting to Tinamous:\n {}".format(e.message))
			return

		if not result.ok:
			self._logger.exception("An error occurred posting to Tinamous:\n {}".format(result.text))
			return

		self._logger.debug("Posted event successfully to Tinamous!")

	def auto_post_picture(self):
		# Don't auto-post if not including a snap-shot picture.
		if self._settings.get(['include_snapshot']):
			self._logger.info("TODO: post picture to Tinamous")

	def auto_post_measurement(self):
		self._logger.info("TODO: post temperatures to Tinamous")

	def post_power_measurements(self, payload):
		# expect payload to be the Pi Power Measurements measurement block.
		senmlFields = []
		senmlFields.append({"n": "V", "u": "V", "v": payload["voltage"]})
		senmlFields.append({"n": "I", "u": "mA", "v": payload["currentMilliAmps"]})
		senmlFields.append({"n": "Power", "u": "W", "v": payload["powerWatts"]})
		senmlFields.append({"n": "Light", "u": "Lux", "v": payload["lightLevel"]})

		for temperature in payload["temperatures"]:
			senmlFields.append({"n": temperature["sensorId"], "u": "°C", "v": temperature["value"]})

		for fan in payload["fans"]:
			# State * 1 to convert boolean to 1 or 0 integer.
			senmlFields.append({"n": "Fan{0}.State".format(fan["fanId"]), "v": fan["state"] * 1})
			senmlFields.append({"n": "Fan{0}.Speed".format(fan["fanId"]), "v": fan["speed"]})

		for gpio in payload["gpioValues"]:
			if gpio["value"]:
				senmlFields.append({"n": "Pin{0}".format(gpio["pin"]), "v": gpio["value"]})

		senml = { "e": senmlFields}

		try:
			result = self.post_to_tinamous("api/v1/senml", senml)
		except Exception, e:
			self._logger.exception("An exception occurred connecting to Tinamous:\n {}".format(e.message))
			return

		if not result.ok:
			self._logger.exception("An error occurred posting Pi Power measurements to Tinamous:\n {}".format(result.text))
			return

		self._logger.debug("Posted power successfully to Tinamous!")

	def post_to_tinamous(self, url_fragment, json):
		account_name = self._settings.get(['tinamous_settings', 'account_name'])
		if not account_name:
			self._logger.exception("Tinamous account name not set.")
			return

		url = "https://{0}.Tinamous.com/{1}".format(account_name, url_fragment)
		self._logger.debug("Attempting post to Tinamous to api: {}".format(url))

		username = self._settings.get(['tinamous_settings', 'username'])
		password = self._settings.get(['tinamous_settings', 'password'])

		return requests.post(url, json=json, auth=(username, password))

# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Tinamous Publisher"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = TinamousPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

