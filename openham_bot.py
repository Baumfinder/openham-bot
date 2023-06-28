import pywikibot
import discord
import os
import time

import openham_bot_config as conf

#page = pywikibot.Page(mediawiki_site, conf.wiki_page_name)
#page.text += "<h3>" + self.result.value + "</h3>by " + self.message.author.name + "<br><blockquote>" + self.message.clean_content + "</blockquote>"
#page.save()

class UserRegistry:
	users: list[int] = []
	
	def __init__(self, serialized: str):
		for uid in serialized.split(" "):
			if uid == "":
				continue
			self.users.append(int(uid))
	
	def serialize(self) -> str:
		result = ""
		for uid in self.users:
			result += str(uid) + " "
		return result
	
class PendingMessage:
	submitted_msg: discord.Message = None
	title: str = None
	approved_by: str = None
	approving_msg: discord.Message = None
	
	def __init__(self, message: discord.Message, title: str):
		self.submitted_msg = message
		self.title = title

pending_msgs: dict[int, PendingMessage] = {}

class TitleInputPopup(discord.ui.Modal, title="Title"):
	result = discord.ui.TextInput(label="Title/Topic of the post")
	message: discord.Message = None
	
	async def on_submit(self, interaction: discord.Interaction):
		message = await discord_client.get_channel(conf.verify_channel_id).send("__" + self.message.author.name + ": **" + self.result.value + "** __\n" + self.message.jump_url)
		await message.add_reaction("✅")
		await message.add_reaction("❌")
		pending_msgs[message.id] = PendingMessage(self.message, self.result.value)
		await interaction.response.send_message("Message has been submitted!", ephemeral=True)


mediawiki_site = pywikibot.Site("openham")

discord_token = open(conf.discord_token_file, "r").readline()
discord_client = discord.Client(intents=discord.Intents.default())
discord_tree = discord.app_commands.CommandTree(discord_client)

user_registry = UserRegistry(open("user_registry.txt", "r").readline())


async def write_to_wiki(pmsg: PendingMessage):
	page = pywikibot.Page(mediawiki_site, conf.wiki_page_name)
	page.text += "<h3>" + pmsg.title + "</h3>\'\'by " + pmsg.submitted_msg.author.name + ", " + pmsg.submitted_msg.created_at.strftime(conf.time_format) + "\'\'<br>" + pmsg.submitted_msg.clean_content
	page.save()
	
	content = str(pmsg.approving_msg.content)
	content += " *Submitted to wiki by " + pmsg.approved_by.name + "!*"
	await pmsg.approving_msg.edit(content=content)
	
	channel = await pmsg.submitted_msg.author.create_dm()
	await channel.send(conf.msgsubmitted + "\nTitle: " + pmsg.title + "\n" + pmsg.submitted_msg.jump_url )

	del pending_msgs[pmsg.approving_msg.id]

@discord_tree.command(name = "ping", description = "Sends Pong.", guild=discord.Object(id=conf.discord_server_id))
async def ping_command(itr: discord.Interaction):
    await itr.response.send_message("Pong!")

@discord_tree.command(name = "clean-verifying-channel", guild=discord.Object(id=conf.discord_server_id))
async def clean_verify_chan_command(itr: discord.Interaction):
	channel = discord_client.get_channel(conf.verify_channel_id)
	
	async for message in channel.history(limit=1000):
		if not message.id in pending_msgs:
			await message.delete()
			time.sleep(0.1)
	
	await itr.response.send_message("Verifying Channel has been cleaned!", ephemeral=True)

#@discord_tree.command(name = "submit", description = "submits message for the wiki", guild=discord.Object(id=conf.discord_server_id))
@discord_tree.context_menu(name="Submit to Wiki", guild=discord.Object(id=conf.discord_server_id))
async def submit_command(itr: discord.Interaction, message: discord.Message):
	title_input = TitleInputPopup()
	title_input.message = message
	await itr.response.send_modal(title_input)

@discord_client.event
async def on_raw_reaction_add(payload):
	if payload.channel_id != conf.verify_channel_id or not payload.message_id in pending_msgs:
		return
		
	pmsg = pending_msgs[payload.message_id]
	this_msg = await discord_client.get_channel(conf.verify_channel_id).fetch_message(payload.message_id)
	
	pmsg.approving_msg = this_msg
	pmsg.approved_by = payload.member
	
	if payload.emoji == discord.PartialEmoji.from_str("✅"):
		if pmsg.submitted_msg.author.id in user_registry.users:
			await write_to_wiki(pmsg)
		else:
			channel = await pmsg.submitted_msg.author.create_dm()
			await channel.send(conf.agreemsg)
		
	elif payload.emoji == discord.PartialEmoji.from_str("❌"):
		content = str(this_msg.content)
		content += " *Dismissed by " + payload.member.name + "!*"
		await this_msg.edit(content=content)
	else: return

@discord_tree.command(name = "agree", guild=discord.Object(id=conf.discord_server_id))
@discord.app_commands.choices(choice=[
	discord.app_commands.Choice(name = "Agree once", value = "once"),
	discord.app_commands.Choice(name = "Agree always", value = "always"),
	discord.app_commands.Choice(name = "Disagree", value = "disagree"),
])
async def agree_command(itr: discord.Interaction, choice: discord.app_commands.Choice[str]):
	if choice.value == "disagree":
		del_msgs: list(int) = []
		for msg_id in pending_msgs:
			if pending_msgs[msg_id].submitted_msg.author.id == itr.user.id:
				del_msgs.append(msg_id)
		
		for msg_id in del_msgs:
			del pending_msgs[msg_id]

		await itr.response.send_message("Disagreed successfully!", ephemeral=True)
		return

	if choice.value == "always":
		user_registry.users.append(itr.user.id)

	ok_msgs: list(int) = []
	for msg_id in pending_msgs:
		if pending_msgs[msg_id].submitted_msg.author.id == itr.user.id:
			ok_msgs.append(msg_id)
	
	for msg_id in ok_msgs:
		await write_to_wiki(pending_msgs[msg_id])
	
	await itr.response.send_message("Agreed successfully!", ephemeral=True)

@discord_client.event
async def on_ready():
    await discord_tree.sync(guild=discord.Object(id=conf.discord_server_id))
    print("Discord ready!")

def cleanup():
	with open("user_registry.txt", "w") as file:
		file.write(user_registry.serialize())

def main():
	mediawiki_site.login()
	print("logged in: " + str(mediawiki_site.logged_in()))

	discord_client.run(discord_token)

if __name__ == "__main__":
	try:
		main()
	finally:
		cleanup()
