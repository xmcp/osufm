#coding=utf-8
import pyquery
import re

result_count_re=re.compile(r'^Displaying \d+ to \d+ of (.+) results.$')

def parse(text):
    pq=pyquery.PyQuery(text,parser='html')

    # get count
    count_text=pq('.pagination')[0].text
    if count_text.startswith('No results found.'):
        return 0,{}
    mat=result_count_re.match(count_text)
    if not mat:
        raise RuntimeError('bad result count string: %s'%count_text)
    count=mat.groups()[0]
    count=-1 if count=='many' else int(count)

    # get beatmaps
    beatmaps=pq('.beatmapListing>.beatmap')
    results=[]
    for ind in range(len(beatmaps)):
        beatmap=beatmaps.eq(ind)
        results.append({
            'id': int(beatmap.attr('id')),
            'title': beatmap.find('.title').text(),
            'mapper': beatmap.find('a[href^="/u/"]').text(),
            'video': bool(beatmap.find('.icon-film')),
            'storyboard': bool(beatmap.find('.icon-picture')),
            #'tags': [tag.text for tag in beatmap.find('.tags>a')],
            'diffs': [diff.attrib['class'][9:].partition('-')[0] for diff in beatmap.find('.difficulties>.diffIcon')],
            'fav': int(beatmap.find('.small-details>.icon-heart')[0].tail.strip().replace(',', '')),
            'play': int(beatmap.find('.small-details>.icon-play')[0].tail.strip().replace(',', '')),
            'rating': (100-float(beatmap.find('.rating>.negative').attr.style[6:-1])) if beatmap.find('.rating>.negative') else -1,
        })

    return count,results