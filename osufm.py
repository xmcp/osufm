#coding=utf-8

import cherrypy
from mako.template import Template
import os
import time
import threading
import requests
import result_parser
from collections import OrderedDict

login_lock=threading.Lock()
APIKEY=os.environ.get('OSU_APIKEY')

def template(name,**kwargs):
    return Template(filename='templates/%s.html'%name,input_encoding='utf-8')

class Website:
    @cherrypy.expose()
    def index(self):
        if 'username' in cherrypy.session:
            return template('index').render(username=cherrypy.session['username'])
        else:
            return template('login').render()

    @cherrypy.expose()
    def login(self,username,password):
        with login_lock: #anti bruteforce
            s=requests.Session()
            res=s.post('https://osu.ppy.sh/forum/ucp.php?mode=login',data={
                'username':username,
                'password':password,
                'login':'Login'}
            )
            res.raise_for_status()
            if res.history: #success
                cherrypy.session['s']=s
                cherrypy.session['username']=username
            else:
                time.sleep(.5)
            raise cherrypy.HTTPRedirect('/')

    @cherrypy.expose()
    def logout(self):
        cherrypy.session.pop('s',None)
        cherrypy.session.pop('anonymous',None)
        cherrypy.session.pop('username',None)
        raise cherrypy.HTTPRedirect('/')

    @cherrypy.expose()
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def search(self):
        if 'username' not in cherrypy.session:
            return {'error':401}

        term=str(cherrypy.request.json['term'])
        filter_std=cherrypy.request.json['filter_std']
        filter_jp=cherrypy.request.json['filter_jp']
        filter_ranked=cherrypy.request.json['filter_ranked']
        romaj=cherrypy.request.json['romaj']

        def fetch_item(t):
            res=cherrypy.session['s'].get('http://osu.ppy.sh/p/beatmaplist',params=dict(
                q=t,
                m=0 if filter_std else -1,
                la=3 if filter_jp else 0,
                r=0 if filter_ranked else 4,
            ))
            res.raise_for_status()
            return result_parser.parse(res.text)

        count,beatmaps=fetch_item(term)

        if romaj:
            assert isinstance(romaj,str)
            rcount,rbeatmaps=fetch_item(romaj)
        else:
            rcount=None
            rbeatmaps=OrderedDict()

        beatmaps.update(rbeatmaps)
        bmap_template=template('search_beatmap')
        for ind,beatmap in enumerate(beatmaps.values()):
            beatmap['html']=bmap_template.render(beatmap=beatmap)
            beatmap['ind']=-ind #better sorting
        return {
            'desc': template('search_desc').render(term=term,count=count,rterm=romaj,rcount=rcount,showing=len(beatmaps)),
            'maplist': list(beatmaps.values()),
        }

    @cherrypy.expose()
    def detail(self,beatmapsetid):
        if 'username' not in cherrypy.session:
            return 'Please log in first. <script>top.location.href="/";</script>'

        res=requests.get(
            'https://osu.ppy.sh/api/get_beatmaps',
            params=dict(
                k=APIKEY,
                s=int(beatmapsetid),
            )
        )
        res.raise_for_status()
        beatmaps=res.json()

        if beatmaps:
            return template('beatmap_detail').render(beatmaps=beatmaps)
        else:
            return 'no result.' #todo: improve

    @cherrypy.expose()
    def down(self,beatmapsetid,video=False):
        if 'username' not in cherrypy.session:
            raise cherrypy.HTTPRedirect('/')

        res=cherrypy.session['s'].get('https://osu.ppy.sh/d/%d%s'%(int(beatmapsetid),'' if video else 'n'),stream=True)
        res.raise_for_status()

        cherrypy.response.headers['Content-Type']='application/x-download'
        cherrypy.response.headers['Content-Disposition']='attachment; filename="%d%s.osz"'%(int(beatmapsetid),'_video' if video else '')

        def addheader(k):
            if k in res.headers:
                cherrypy.response.headers[k]=res.headers[k]
        addheader('Content-Length')
        addheader('Content-Encoding')

        def extract():
            yield from res.raw.stream(64*1024,decode_content=False)
        return extract()


if APIKEY is None:
    print('WARNING: OSU_APIKEY not set.')

cherrypy.quickstart(Website(),'/',{
    'global': {
        'server.socket_host': '0.0.0.0',
        'server.socket_port': int(os.environ.get('PORT',80)),
        'engine.autoreload.on': False,
    },
    '/': {
        'tools.sessions.on': True,
        'tools.gzip.on': True,
        'tools.response_headers.on':True,
    },
    '/static': {
        'tools.staticdir.on':True,
        'tools.staticdir.dir':os.path.join(os.getcwd(),'static'),
        'tools.response_headers.headers': [
            ('Cache-Control','max-age=86400'),
        ],
    },
    '/down': {
        'response.stream': True,
        'tools.gzip.on': False,
    }
})