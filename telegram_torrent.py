#-*-coding:utf-8-*-
#!/usr/bin/python
import sys
import os
import feedparser
import telepot
import json
import random
import string
import urllib
from os.path import expanduser
from apscheduler.schedulers.background import BackgroundScheduler
from telepot.delegate import per_chat_id, create_open, pave_event_space

CONFIG_FILE = 'setting.json'

class DelugeAgent:

    def __init__(self, sender):
        self.STATUS_SEED = 'Seeding'
        self.STATUS_DOWN = 'Downloading'
        self.STATUS_ERR = 'Error'  # Need Verification
        self.weightList = {}
        self.sender = sender

    def download(self, item):
        os.system("deluge-console add " + item)

    def getCurrentList(self):
        return os.popen('deluge-console info').read()

    def printElement(self, e):
        outString = '이름: ' + e['title'] + \
            '\n' + '상태: ' + e['status'] + '\n'
        outString += '진행: ' + e['progress'] + '\n'
        outString += '\n'
        return outString

    def parseList(self, result):
        if not result:
            return
        outList = []
        for entry in result.split('\n \n'):
            title = entry[entry.index('Name:') + 6:entry.index('ID:') - 1]
            status = entry[entry.index('State:'):].split(' ')[1]
            ID = entry[entry.index('ID:') + 4:entry.index('State:') - 1]
            if status == self.STATUS_DOWN:
                progress = entry[entry.index(
                    'Progress:') + 10:entry.index('% [') + 1]
            else:
                progress = '0.00%'
            element = {'title': title, 'status': status,
                       'ID': ID, 'progress': progress}
            outList.append(element)
        return outList

    def isOld(self, ID, progress):
        """weightList = {ID:[%,w],..}"""
        if ID in self.weightList:
            if self.weightList[ID][0] == progress:
                self.weightList[ID][1] += 1
            else:
                self.weightList[ID][0] = progress
                self.weightList[ID][1] = 1
            if self.weightList[ID][1] > 3:
                return True
        else:
            self.weightList[ID] = [progress, 1]
            return False
        return False

    def check_torrents(self):
        currentList = self.getCurrentList()
        outList = self.parseList(currentList)
        if not bool(outList):
            self.sender.sendMessage('토렌트 목록이 비어 있습니다.')
            scheduler.remove_all_jobs()
            self.weightList.clear()
            return
        for e in outList:
            if e['status'] == self.STATUS_SEED:
                self.sender.sendMessage(
                    'Download completed: {0}'.format(e['title']))
                self.removeFromList(e['ID'])
            elif e['status'] == self.STATUS_ERR:
                self.sender.sendMessage(
                    'Download canceled (Error): {0}\n'.format(e['title']))
                self.removeFromList(e['ID'])
            else:
                if self.isOld(e['ID'], e['progress']):
                    self.sender.sendMessage(
                        'Download canceled (pending): {0}\n'.format(e['title']))
                    self.removeFromList(e['ID'])
        return

    def removeFromList(self, ID):
        if ID in self.weightList:
            del self.weightList[ID]
        os.system("deluge-console del " + ID)


class TransmissionAgent:

    def __init__(self, sender):
        self.STATUS_SEED = 'Seeding'
        self.STATUS_ERR = 'Error'  # Need Verification
        self.weightList = {}
        self.sender = sender
        cmd = 'transmission-remote '
        if TRANSMISSION_ID_PW:
            cmd = cmd + '-n ' + TRANSMISSION_ID_PW + ' '
        else:
            cmd = cmd + '-n ' + 'transmission:transmission' + ' '
        self.transmissionCmd = cmd

    def download(self, magnet):
        if TRANSMISSION_PORT:
            pcmd = '-p ' + TRANSMISSION_PORT + ' '
        else:
            pcmd = ''
        if DOWNLOAD_PATH:
            wcmd = '-w ' + DOWNLOAD_PATH + ' '
        else:
            wcmd = ''
        os.system(self.transmissionCmd + pcmd + wcmd + '-a ' + "\"" + magnet + "\"")

    def getCurrentList(self):
        l = os.popen(self.transmissionCmd + '-l').read()
        rowList = l.split('\n')
        if len(rowList) < 4:
            return
        else:
            return l

    def printElement(self, e):
        outString = '이름: ' + e['title'] + \
            '\n' + '상태: ' + e['status'] + '\n'
        outString += '진행: ' + e['progress'] + '\n'
        outString += '\n'
        return outString

    def parseList(self, result):
        if not result:
            return
        outList = []
        resultlist = result.split('\n')
        titlelist = resultlist[0]
        resultlist = resultlist[1:-2]
        for entry in resultlist:
            title = entry[titlelist.index('Name'):].strip()
            status = entry[titlelist.index(
                'Status'):titlelist.index('Name') - 1].strip()
            progress = entry[titlelist.index(
                'Done'):titlelist.index('Done') + 4].strip()
            id_ = entry[titlelist.index(
                'ID'):titlelist.index('Done') - 1].strip()
            if id_[-1:] == '*':
                id_ = id_[:-1]
            element = {'title': title, 'status': status,
                       'ID': id_, 'progress': progress}
            outList.append(element)
        return outList

    def removeFromList(self, ID):
        if ID in self.weightList:
            del self.weightList[ID]
        os.system(self.transmissionCmd + '-t ' + ID + ' -r')

    def isOld(self, ID, progress):
        """weightList = {ID:[%,w],..}"""
        if ID in self.weightList:
            if self.weightList[ID][0] == progress:
                self.weightList[ID][1] += 1
            else:
                self.weightList[ID][0] = progress
                self.weightList[ID][1] = 1
            if self.weightList[ID][1] > 3:
                return True
        else:
            self.weightList[ID] = [progress, 1]
            return False
        return False

    def check_torrents(self):
        currentList = self.getCurrentList()
        outList = self.parseList(currentList)
        if not bool(outList):
            self.sender.sendMessage('토렌트 목록이 비어 있습니다.')
            scheduler.remove_all_jobs()
            self.weightList.clear()
            return
        for e in outList:
            if e['status'] == self.STATUS_SEED:
                self.sender.sendMessage(
                    'Download completed: {0}'.format(e['title']))
                self.removeFromList(e['ID'])
            elif e['status'] == self.STATUS_ERR:
                self.sender.sendMessage(
                    'Download canceled (Error): {0}\n'.format(e['title']))
                self.removeFromList(e['ID'])
            else:
                if self.isOld(e['ID'], e['progress']):
                    self.sender.sendMessage(
                        'Download canceled (pending): {0}\n'.format(e['title']))
                    self.removeFromList(e['ID'])
        return


class Torrenter(telepot.helper.ChatHandler):
    YES = '<OK>'
    NO = '<NO>'
    MENU0 = '홈'
    MENU1 = '토렌트 키워드 검색'
    MENU1_1 = '검색어 입력'
    MENU1_2 = '항목을 선택하십시오.'
    MENU2 = '토렌트 리스트'
    MENU3 = '토렌트 최신영화 검색'
    MENU4 = '다음 페이지'
    MENU5 = '이전 페이지'
    rssUrl = """https://godpeople.or.kr/torrent/rss.php?site=tf&table=tmovie"""
    GREETING = "메뉴를 선택해주세요"
    global scheduler
    global DOWNLOAD_PATH

    mode = ''
    navi = feedparser.FeedParserDict()

    def __init__(self, *args, **kwargs):
        super(Torrenter, self).__init__(*args, **kwargs)
        self.agent = self.createAgent(AGENT_TYPE)

    def createAgent(self, agentType):
        if agentType == 'deluge':
            return DelugeAgent(self.sender)
        if agentType == 'transmission':
            return TransmissionAgent(self.sender)
        raise ('잘못된 토렌트 클라이언트')

    def open(self, initial_msg, seed):
        self.menu()

    def menu(self):
        mode = ''
        show_keyboard = {'keyboard': [
            [self.MENU1], [self.MENU3], [self.MENU2], [self.MENU0]]}
        self.sender.sendMessage(self.GREETING, reply_markup=show_keyboard)

    def yes_or_no(self, comment):
        show_keyboard = {'keyboard': [[self.YES, self.NO], [self.MENU0]]}
        self.sender.sendMessage(comment, reply_markup=show_keyboard)

    def tor_get_keyword(self):
        self.mode = self.MENU1_1
        self.sender.sendMessage('검색할 단어를 입력해주세요')

    def put_menu_button(self, l):
        if self.page == 1:
            menulist = [self.MENU4, self.MENU0]
        else:
            menulist = [self.MENU5, self.MENU4, self.MENU0]
        l.append(menulist)
        return l

    def tor_search(self, keyword, page):
        self.mode = ''
        self.sender.sendMessage(keyword + ' 토렌트 검색중...')
        #self.navi = feedparser.parse(self.rssUrl + urllib.quote(keyword))
        keyUrl = ''
        if keyword:
            keyUrl = "&key=" + urllib.quote(keyword.encode('utf-8'))
            
        self.navi = feedparser.parse(self.rssUrl + keyUrl + "&page=" + str(page))

        outList = []
        if not self.navi.entries:
            self.sender.sendMessage('죄송합니다. 검색결과가 없습니다.')
            self.mode = self.MENU1_1
            return

        for (i, entry) in enumerate(self.navi.entries):
            #if i == 10:
            #    break 
            try:
                title = str(i + 1) + ". " + entry.title
            except:
                continue

            templist = []
            templist.append(title)
            outList.append(templist)

        self.page = page
        self.keyword = keyword
        show_keyboard = {'keyboard': self.put_menu_button(outList)}
        self.sender.sendMessage('아래에서 하나를 선택하십시오.',
                                reply_markup=show_keyboard)
        self.mode = self.MENU1_2

    def tor_download(self, selected):
        self.mode = ''

        if not selected.isdigit():
            self.menu()
            return
	
        index = int(selected.split('.')[0]) - 1
        magnet = self.navi.entries[index].link
        self.agent.download(magnet)
        self.sender.sendMessage('다운로드를 시작합니다.')
        self.navi.clear()
        if not scheduler.get_jobs():
            scheduler.add_job(self.agent.check_torrents, 'interval', minutes=1)
        self.menu()

    def tor_show_list(self):
        self.mode = ''
        self.sender.sendMessage('토렌트 리스트를 확인하겠습니다...')
        result = self.agent.getCurrentList()
        if not result:
            self.sender.sendMessage('토렌트 목록이 비어 있습니다.')
            self.menu()
            return
        outList = self.agent.parseList(result)
        for e in outList:
            self.sender.sendMessage(self.agent.printElement(e))

    def handle_command(self, command):
        if command == self.MENU0:
            self.menu()
        elif command == self.MENU1:
            self.tor_get_keyword()
        elif command == self.MENU2:
            self.tor_show_list()
        elif command == self.MENU3:
            self.tor_search("", 1)
        elif command == self.MENU4:
            self.tor_search(self.keyword, self.page+1)
        elif command == self.MENU5:
            self.tor_search(self.keyword, self.page-1)
        elif self.mode == self.MENU1_1:  # Get Keyword
            self.tor_search(command, 1)
        elif self.mode == self.MENU1_2:  # Download Torrent
            self.tor_download(command)

    def handle_smifile(self, file_id, file_name):
        try:
            self.sender.sendMessage('자막 파일 저장 중..')
            bot.download_file(file_id, DOWNLOAD_PATH + file_name)
        except Exception as inst:
            self.sender.sendMessage('ERORR: {0}'.format(inst))
            return
        self.sender.sendMessage('완료')

    def handle_seedfile(self, file_id, file_name):
        try:
            self.sender.sendMessage('토렌트 파일 저장 중..')
            generated_file_path = DOWNLOAD_PATH + "/" + \
                "".join(random.sample(string.ascii_letters, 8)) + ".torrent"
            bot.download_file(file_id, generated_file_path)
            self.agent.download(generated_file_path)
            os.system("rm " + generated_file_path)
            if not scheduler.get_jobs():
                scheduler.add_job(self.agent.check_torrents,
                                  'interval', minutes=1)
        except Exception as inst:
            self.sender.sendMessage('ERORR: {0}'.format(inst))
            return
        self.sender.sendMessage('다운로드를 시작합니다.')

    def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        # Check ID
        if not chat_id in VALID_USERS:
            print("Permission Denied")
            return

        if content_type is 'text':
            #print(msg['text'])
            self.handle_command(msg['text'])
            return

        if content_type is 'document':
            file_name = msg['document']['file_name']
            if file_name[-3:] == 'smi':
                file_id = msg['document']['file_id']
                self.handle_smifile(file_id, file_name)
                return
            if file_name[-7:] == 'torrent':
                file_id = msg['document']['file_id']
                self.handle_seedfile(file_id, file_name)
                return
            self.sender.sendMessage('유효하지 않은 파일 입니다.')
            return

        self.sender.sendMessage('유효하지 않은 파일 입니다.')

    def on_close(self, exception):
        pass


def parseConfig(filename):
    path = os.path.dirname(os.path.realpath(__file__)) + '/' + filename
    f = open(path, 'r')
    js = json.loads(f.read())
    f.close()
    return js


def getConfig(config):
    global TOKEN
    global AGENT_TYPE
    global VALID_USERS
    global DOWNLOAD_PATH
    TOKEN = config['common']['token']
    AGENT_TYPE = config['common']['agent_type']
    VALID_USERS = config['common']['valid_users']
    DOWNLOAD_PATH = config['common']['download_path']
    if DOWNLOAD_PATH[0] == '~':
        DOWNLOAD_PATH = expanduser('~') + DOWNLOAD_PATH[1:]
    if AGENT_TYPE == 'transmission':
        global TRANSMISSION_ID_PW
        global TRANSMISSION_PORT
        TRANSMISSION_ID_PW = config['transmission']['id_pw']
        TRANSMISSION_PORT = config['transmission']['port']

reload(sys)
sys.setdefaultencoding("utf-8")
config = parseConfig(CONFIG_FILE)
if not bool(config):
    print("Err: 설정 파일을 찾을 수 없습니다.")
    exit()
getConfig(config)
scheduler = BackgroundScheduler()
scheduler.start()
bot = telepot.DelegatorBot(TOKEN, [
    pave_event_space()(
        per_chat_id(), create_open, Torrenter, timeout=120),
])
bot.message_loop(run_forever='Listening ...')
