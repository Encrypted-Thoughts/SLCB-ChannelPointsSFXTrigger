# -*- coding: utf-8 -*-

#---------------------------
#   Import Libraries
#---------------------------
import clr, codecs, json, os, re, sys, threading, datetime, System

# Include the assembly with the name AnkhBotR2
clr.AddReference([asbly for asbly in System.AppDomain.CurrentDomain.GetAssemblies() if "AnkhBotR2" in str(asbly)][0])
import AnkhBotR2

clr.AddReference("IronPython.Modules.dll")
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + r"\References")
clr.AddReference(r"TwitchLib.PubSub.dll")
from TwitchLib.PubSub import TwitchPubSub

#---------------------------
#   [Required] Script Information
#---------------------------
ScriptName = "Twitch Channel Points SFX Trigger"
Website = "https://www.twitch.tv/EncryptedThoughts"
Description = "Script to trigger SFX on channel point reward redemptions."
Creator = "EncryptedThoughts"
Version = "2.0.0.0"

#---------------------------
#   Define Global Variables
#---------------------------
SettingsFile = os.path.join(os.path.dirname(__file__), "settings.json")
ReadMe = os.path.join(os.path.dirname(__file__), "README.md")
EventReceiver = None
ThreadQueue = []
CurrentThread = None
PlayNextAt = datetime.datetime.now()
RewardCount = 15

#---------------------------------------
# Classes
#---------------------------------------
class Settings(object):
    def __init__(self, SettingsFile=None):
        if SettingsFile and os.path.isfile(SettingsFile):
            with codecs.open(SettingsFile, encoding="utf-8-sig", mode="r") as f:
                self.__dict__ = json.load(f, encoding="utf-8")
        else:
            self.EnableDebug = False
            for i in range(1, RewardCount + 1):
                setattr(self, "TwitchReward" + str(i) + "Name", "")
                setattr(self, "TwitchReward" + str(i) + "ActivationType", "Immediate")
                setattr(self, "SFX" + str(i) + "Path", "")
                setattr(self, "SFX" + str(i) + "Volume", 100)
                setattr(self, "SFX" + str(i) + "Delay", 10)

    def Reload(self, jsondata):
        self.__dict__ = json.loads(jsondata, encoding="utf-8")
        return

    def Save(self, SettingsFile):
        try:
            with codecs.open(SettingsFile, encoding="utf-8-sig", mode="w+") as f:
                json.dump(self.__dict__, f, encoding="utf-8")
            with codecs.open(SettingsFile.replace("json", "js"), encoding="utf-8-sig", mode="w+") as f:
                f.write("var settings = {0};".format(json.dumps(self.__dict__, encoding='utf-8')))
        except:
            Parent.Log(ScriptName, "Failed to save settings to file.")
        return

#---------------------------
#   [Required] Initialize Data (Only called on load)
#---------------------------
def Init():
    global ScriptSettings
    ScriptSettings = Settings(SettingsFile)
    ScriptSettings.Save(SettingsFile)

    return

#---------------------------
#   [Required] Execute Data / Process messages
#---------------------------
def Execute(data):
    return

#---------------------------
#   [Required] Tick method (Gets called during every iteration even when there is no incoming data)
#---------------------------
def Tick():
    global PlayNextAt
    if PlayNextAt > datetime.datetime.now():
        return

    global CurrentThread
    if CurrentThread and CurrentThread.isAlive() == False:
        CurrentThread = None

    if CurrentThread == None and len(ThreadQueue) > 0:
        if ScriptSettings.EnableDebug:
            Parent.Log(ScriptName, "Starting new thread. " + str(PlayNextAt))
        CurrentThread = ThreadQueue.pop(0)
        CurrentThread.start()
        
    return

#---------------------------
#   [Optional] Parse method (Allows you to create your own custom $parameters) 
#---------------------------
def Parse(parseString, userid, username, targetid, targetname, message):
    return parseString

#---------------------------
#   [Optional] Reload Settings (Called when a user clicks the Save Settings button in the Chatbot UI)
#---------------------------
def ReloadSettings(jsonData):
    if ScriptSettings.EnableDebug:
        Parent.Log(ScriptName, "Saving settings.")

    try:
        ScriptSettings.__dict__ = json.loads(jsonData)
        ScriptSettings.Save(SettingsFile)

        if ScriptSettings.EnableDebug:
            Parent.Log(ScriptName, "Settings saved successfully")
    except Exception as e:
        if ScriptSettings.EnableDebug:
            Parent.Log(ScriptName, str(e))

    return

#---------------------------
#   [Optional] Unload (Called when a user reloads their scripts or closes the bot / cleanup stuff)
#---------------------------
def Unload():
    StopEventReceiver()
    return

#---------------------------
#   [Optional] ScriptToggled (Notifies you when a user disables your script or enables it)
#---------------------------
def ScriptToggled(state):
    if state:
        if EventReceiver is None:
            RestartEventReceiver()
    else:
        StopEventReceiver()

    return

#---------------------------
#   StartEventReceiver (Start twitch pubsub event receiver)
#---------------------------
def StartEventReceiver():
    if ScriptSettings.EnableDebug:
        Parent.Log(ScriptName, "Starting receiver")

    global EventReceiver
    EventReceiver = TwitchPubSub()
    EventReceiver.OnPubSubServiceConnected += EventReceiverConnected
    EventReceiver.OnRewardRedeemed += EventReceiverRewardRedeemed

    try:
        EventReceiver.Connect()
    except Exception as e:
        Parent.Log(ScriptName, "Unable to start event receiver. Exception: " + str(e))

#---------------------------
#   StopEventReceiver (Stop twitch pubsub event receiver)
#---------------------------
def StopEventReceiver():
    global EventReceiver
    try:
        if EventReceiver is None:
            return
        EventReceiver.Disconnect()
        if ScriptSettings.EnableDebug:
            Parent.Log(ScriptName, "Event receiver disconnected")
        EventReceiver = None

    except Exception as e:
        if ScriptSettings.EnableDebug:
            Parent.Log(ScriptName, "Event receiver already disconnected. Exception: " + str(e))

#---------------------------
#   RestartEventReceiver (Restart event receiver cleanly)
#---------------------------
def RestartEventReceiver():
    StopEventReceiver()
    StartEventReceiver()

#---------------------------
#   EventReceiverConnected (Twitch pubsub event callback for on connected event. Needs a valid UserID and AccessToken to function properly.)
#---------------------------
def EventReceiverConnected(sender, e):
    oauth = AnkhBotR2.Managers.GlobalManager.Instance.VMLocator.StreamerLogin.Token.replace("oauth:", "")

    headers = { "Authorization": 'OAuth ' + oauth }
    data = json.loads(Parent.GetRequest("https://id.twitch.tv/oauth2/validate", headers))

    userid = json.loads(data["response"])['user_id']

    if ScriptSettings.EnableDebug:
        Parent.Log(ScriptName, "Event receiver connected, sending topics for channel id: " + str(userid))

    EventReceiver.ListenToRewards(userid)
    EventReceiver.SendTopics(oauth)
    return

#---------------------------
#   EventReceiverRewardRedeemed (Twitch pubsub event callback for a detected redeemed channel point reward.)
#---------------------------
def EventReceiverRewardRedeemed(sender, e):
    if ScriptSettings.EnableDebug:
        Parent.Log(ScriptName, "Event triggered: " + str(e.TimeStamp) + " ChannelId: " + str(e.ChannelId) + " Login: " + str(e.Login) + " DisplayName: " + str(e.DisplayName) + " Message: " + str(e.Message) + " RewardId: " + str(e.RewardId) + " RewardTitle: " + str(e.RewardTitle) + " RewardPrompt: " + str(e.RewardPrompt) + " RewardCost: " + str(e.RewardCost) + " Status: " + str(e.Status))

    Parent.Log(ScriptName, str(RewardCount))
    for i in range(1, RewardCount + 1):
        rewardName = getattr(ScriptSettings, "TwitchReward" + str(i) + "Name")
        if e.RewardTitle ==  rewardName and not rewardName.isspace():
            rewardType = getattr(ScriptSettings, "TwitchReward" + str(i) + "ActivationType")
            if (rewardType == "Immediate" and "FULFILLED" in e.Status) or (rewardType == r"On Reward Queue Accept/Reject" and "ACTION_TAKEN" in e.Status):
                ThreadQueue.append(threading.Thread(target=RewardRedeemedWorker,args=(
                    getattr(ScriptSettings, "SFX" + str(i) + "Path"), 
                    getattr(ScriptSettings, "SFX" + str(i) + "Volume"), 
                    getattr(ScriptSettings, "SFX" + str(i) + "Delay"),)))

    return

#---------------------------
#   RewardRedeemedWorker (Worker function to be spun off into its own thread to complete without blocking the rest of script execution.)
#---------------------------
def RewardRedeemedWorker(path, volume, delay):
    if ScriptSettings.EnableDebug:
        Parent.Log(ScriptName, path + " " + str(volume) + " " + str(delay))

    Parent.PlaySound(path, volume/100.0)
    global PlayNextAt
    PlayNextAt = datetime.datetime.now() + datetime.timedelta(0, delay)

#---------------------------
#   OpenReadme (Attached to settings button to open the readme file in the script bin.)
#---------------------------
def OpenReadme():
    os.startfile(ReadMe)