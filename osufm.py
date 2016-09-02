#coding=utf-8
import cherrypy
from mako.template import Template
import os
import time
import threading
import requests
import result_parser

login_lock=threading.Lock()

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
        term=str(cherrypy.request.json['term'])
        filter_std=cherrypy.request.json['filter_std']
        filter_jp=cherrypy.request.json['filter_jp']
        filter_ranked=cherrypy.request.json['filter_ranked']
        romaj=cherrypy.request.json['romaj']
        res=cherrypy.session['s'].get('http://osu.ppy.sh/p/beatmaplist',params=dict(
            q=term,
            m=0 if filter_std else -1,
            la=3 if filter_jp else 0,
            r=0 if filter_ranked else 4,
        ))
        res.raise_for_status()
        count,beatmaps=result_parser.parse(res.text)
        bmap_template=template('search_beatmap')
        for beatmap in beatmaps:
            beatmap['html']=bmap_template.render(beatmap=beatmap)
        return {
            'desc': template('search_desc').render(term=term,count=count),
            'maplist': beatmaps,
        }


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
    }
})