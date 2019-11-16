import os, string, re, unicodedata, sys, urllib, urlparse, inspect, time

BLANK_FIELD = '\x7f'

NFO_TEXT_REGEX_1 = re.compile(
    r'&(?![A-Za-z]+[0-9]*;|#[0-9]+;|#x[0-9a-fA-F]+;)'
)
NFO_TEXT_REGEX_2 = re.compile(r'^\s*<.*/>[\r\n]+', flags=re.MULTILINE)
RATING_REGEX_1 = re.compile(
    r'(?:Rated\s)?(?P<mpaa>[A-z0-9-+/.]+(?:\s[0-9]+[A-z]?)?)?'
)
RATING_REGEX_2 = re.compile(r'\s*\(.*?\)')

def Start():pass

def GetParentDir(directories):
  parent_dirs = {}
  for d in directories:
    try:
      parent = os.path.split(d)[0]
      parent_dirs[parent] = True
    except:pass
  
  if parent_dirs.has_key(''):
    del parent_dirs['']
  return parent_dirs

#searches for a valid nfo file, loads it up ands returns it 
def FindNfo(paths, nfo):
  for path in paths:
    for f in os.listdir(path):
      (fn, ext) = os.path.splitext(f)
      if(fn == nfo and not fn.startswith('.') and ext[1:] == "nfo"):
        nfo_file = os.path.join(path, f)
        nfo_text = Core.storage.load(nfo_file)
        # work around failing XML parses for things with &'s in them. This may need to go farther than just &'s....
        nfo_text = NFO_TEXT_REGEX_1.sub('&amp;', nfo_text)
        # remove empty xml tags from nfo
        nfo_text = NFO_TEXT_REGEX_2.sub('', nfo_text)

        nfo_text_lower = nfo_text.lower()
        if nfo_text_lower.count('<'+nfo) > 0 and nfo_text_lower.count('</'+nfo+'>') > 0:
            # Remove URLs (or other stuff) at the end of the XML file
          content = nfo_text.rsplit('</'+nfo+'>', 1)[0]
          nfo_text = '{content}</{nfo}>'.format(content=content,nfo=nfo)

          # likely a kodi nfo file
          try:
            nfo_xml = XML.ElementFromString(nfo_text).xpath('//'+nfo)[0]
          except:
            Log("ERROR: Cant parse %s from XML in %s Skipping!", nfo, nfo_file)
            continue

          nfo_xml = remove_empty_tags(nfo_xml)
          Log("%s data loaded from file %s", nfo, nfo_file)
          return nfo_xml

def remove_empty_tags(document):
  """
  Removes empty XML tags.

  :param document: An HTML element object.
      see: http://lxml.de/api/lxml.etree._Element-class.html
  :return:
  """
  empty_tags = []
  for xml_tag in document.iter('*'):
    if not(len(xml_tag) or (xml_tag.text and xml_tag.text.strip())):
      empty_tags.append(xml_tag.tag)
      xml_tag.getparent().remove(xml_tag)
  #Log("Empty XMLTags removed: {number} {tags}".format(number=len(empty_tags) or None, tags=sorted(set(empty_tags)) or ''))
  return document
    
#searches for artist.nfo in Artist folder and adds fields to the metadata
def ReadArtistNfo(metadata, paths):
  nfo_xml = FindNfo(paths,'artist')
  if nfo_xml:
    metadata.summary = get_tag_nfo(nfo_xml, 'biography', lg=True)
    add_tags_nfo(nfo_xml, metadata.genres, 'genre', lg=True)
    add_tags_nfo(nfo_xml, metadata.styles, 'style', lg=True)
    add_tags_nfo(nfo_xml, metadata.moods, 'mood', lg=True)
    add_tags_nfo(nfo_xml, metadata.collections, 'tag', lg=True) #works
    add_subtags_nfo(nfo_xml, metadata.similar, 'artist', 'name', lg=True)
    add_concerts_nfo(nfo_xml, metadata.concerts, lg=True)

#searches for album.nfo in Album folder and adds fields to the metadata
def ReadAlbumNfo(metadata, paths):
  nfo_xml = FindNfo(paths,'album')
  if nfo_xml:
    metadata.summary = get_tag_nfo(nfo_xml, 'review', lg=True)
    metadata.studio = get_tag_nfo(nfo_xml, 'label', lg=True)    
    metadata.originally_available_at =  get_date_nfo(nfo_xml, 'releasedate', lg=True)
    add_tags_nfo(nfo_xml, metadata.genres, 'genre', lg=True)
    add_tags_nfo(nfo_xml, metadata.styles, 'style', lg=True)
    add_tags_nfo(nfo_xml, metadata.moods, 'mood', lg=True)
    add_tags_nfo(nfo_xml, metadata.collections, 'tag', lg=True) #doesn't work?
    
    return get_tracks_nfo(nfo_xml, lg=True)

#returns existing value or if none, gets from nfo, routes all single field gets through here, so will handle any errors and carry on
def get_tag_nfo(nfo_xml, name, value=None, lg=False):
  try:
    if not value or value == BLANK_FIELD:
      value = nfo_xml.xpath(name)[0].text.strip()
      if lg: Log("found <%s> tag = %s... from nfo", name, value[:50])
    else:
      if lg: Log("found existing <%s> tag = %s... ignoring nfo", name, value[:50])
  except:
    #if lg: Log("Exception getting <%s> tag from nfo", name)
    pass
  return value
        
#returns existing date or if none, gets from nfo 
def get_date_nfo(nfo_xml, name, value=None, lg=False):
  try:
    if not value:
      dt = get_tag_nfo(nfo_xml, name)
      value = Datetime.ParseDate(dt, '%Y-%m-%d').date()
      if lg: Log("added <%s> tag = %s... from nfo", name, value)
    else:
      if lg: Log("found existing <%s> date = %s, ignoring nfo", name, value)
  except:
    if lg: Log("Exception getting <%s> date from nfo", name)
    pass
  return value

#returns existing date or if none, gets from nfo 
def get_float_nfo(nfo_xml, name, value=None, lg=False):
  try:
    if not value:
      f = get_tag_nfo(nfo_xml, name)
      value = float(f)
      if lg: Log("found <%s> float = %s... from nfo", name, value)
    else:
      if lg: Log("found existing <%s> float = %s, ignoring nfo", name, value)
  except:
    if lg: Log("Exception getting <%s> float from nfo", name)
    pass
  return value

#returns existing rating or if none, gets from nfo and * 10 and rets as int
def get_rating_nfo(nfo_xml, name, value=None, lg=False):
  try:
    if not value:
      rating = get_float_nfo(nfo_xml, name)
      value = int(rating * 10 + 0.5)
      if lg: Log("found <%s> rating = %s... from nfo", name, value)
    else:
      if lg: Log("found existing <%s> rating = %s, ignoring nfo", name, value)
  except:
    if lg: Log("Exception getting <%s> rating from nfo", name)
    pass
  return value

    
#adds tags from nfo if no existing ones or clr => replace with new ones
def add_tags_nfo(nfo_xml, node, name, clr=True, lg=False):
  try:
    if clr:
      node.clear()
    elif node:
      if lg: Log("found %s existing <%s> tags, ignoring nfo", len(node), name)
      return
    tags = nfo_xml.xpath(name)
    [node.add(t.strip()) for tagXML in tags for t in tagXML.text.split('/')]
    if lg: Log("added %s <%s> tags from nfo", len(node), name)
  except:
    if lg: Log("exception adding <%s> tags from nfo", name)
    pass

#add value to hash using key, only IF value not empty
def add_hash(hash, key, value):
  if value: hash[key] = value

def add_subtags_nfo(nfo_xml, node, tagname, subtagname, clr=True, lg=False):
  try:
    if clr:
      node.clear()
    elif node:
      if lg: Log("found %s existing <%s> tags, ignoring nfo", len(node), tagname)
      return
    tags = nfo_xml.xpath(tagname)
    for tagXML in tags:
      subtag = get_tag_nfo(tagXML, subtagname)
      node.add(subtag.strip())
      #Log("tag=%s", subtag)
    if lg: Log("added %s <%s> tags from nfo", len(node), tagname)
  except Exception as e:
    if lg: Log("exception adding <%s> tags from nfo=%s", tagname, e)
    pass


#adds tags from nfo if no existing ones or clr => replace with new ones
def get_tracks_nfo(nfo_xml, tagname='track', lg=False):
  nfo_tracks={}
  try:
    tags = nfo_xml.xpath(tagname)
    for tagXML in tags:
      title = get_tag_nfo(tagXML, 'title')
      if title:
        nfo_track={}
        add_hash(nfo_track, 'rating', get_rating_nfo(tagXML, 'rating'))
        add_hash(nfo_track, 'review', get_tag_nfo(tagXML, 'review'))
        #add_hash(nfo_track, 'mbid', get_tag_nfo(tagXML, 'musicBrainzTrackID', None, False))
        #add_hash(nfo_track, 'index', get_tag_nfo(tagXML, 'position', None, False))
        if nfo_track: #only add if track dict has entries
          nfo_track['title'] = title
          nfo_tracks[fuzzy(title)] = nfo_track
          #Log("found <%s.rating> tag in nfo : name = %s : rating = %s : ", tagname, title, nfo_track['rating'])
    if lg: Log("found %s <%s.rating> tags with rating in nfo", len(nfo_tracks), tagname) 
    return nfo_tracks 
  except Exception as e:
    if lg: Log("error setting %s tags from nfo = %s", tagname, e)
    pass

#adds tags from nfo if no existing ones or clr => replace with new ones
def add_concerts_nfo(nfo_xml, node, tagname='concert', clr=True, lg=False):
  if clr:
    node.clear()
  elif node:
    if lg: Log("found %s existing <%s> tags, ignoring nfo", len(node), tagname)
    return
  try:
    tags = nfo_xml.xpath(tagname)
    for tagXML in tags:
      title = get_tag_nfo(tagXML, 'title')
      if title:
        concert = node.new()
        concert.title = title
        concert.venue = get_tag_nfo(tagXML, 'venue')
        concert.city = get_tag_nfo(tagXML, 'city')
        concert.country = get_tag_nfo(tagXML, 'country')
        concert.date = get_date_nfo(tagXML, 'date')
        concert.url = get_tag_nfo(tagXML, 'url') 
    if lg: Log("found %s <%s> tags in nfo", len(node), tagname) 
  except Exception as e:
    if lg: Log("error setting %s tags from nfo = %s", tagname, e)
    pass

#remove non alphanumeric chars + lcase string to simplify song name matches
def fuzzy(tag):
  try:
    tag = tag.lower();
    ftag = re.sub('[^0-9a-z]+', '', tag)
    if len(ftag) >= 4: return ftag 
  except:
    pass
  return tag

class KodiArtistNfo(Agent.Artist):
  contributes_to = ['com.plexapp.agents.none']
  primary_provider = False
  persist_stored_files = False
  name = "Kodi Nfo (Artists)"
  
  def search(self, results, media, lang):
    results.Append(MetadataSearchResult(id = 'null', name=media.artist, score = 100))
    
  def update(self, metadata, media, lang, child_guid=None):
    Log("started artist nfo import")
    dirs = {}
    #LogObj(metadata.similar, 'artist.metadata.similar')
   
    for a in media.albums:
      for t in media.albums[a].tracks:
        track = media.albums[a].tracks[t].items[0]
        dirs[os.path.dirname(track.parts[0].file)] = True
    artist_dirs = GetParentDir(dirs)    
    
    nfo_concerts = ReadArtistNfo(metadata, artist_dirs) 
    Log("finished artist nfo import")

    
class KodiAlbumNfo(Agent.Album):
  name = "Kodi Nfo (Albums)"
  primary_provider = False
  persist_stored_files = False
  contributes_to = ['com.plexapp.agents.none']
  
  def search(self, results, media, lang):
    results.Append(MetadataSearchResult(id = 'null', score = 100))
    
  def update(self, metadata, media, lang):
    Log("started album nfo import")
    
    dirs = {}
    for t in media.tracks:
      track = media.tracks[t].items[0]
      dirs[os.path.dirname(track.parts[0].file)] = True
    
    nfo_tracks = ReadAlbumNfo(metadata, dirs)

    if (nfo_tracks):
      Log('len: media.tracks= %s : media.children=%s : metadata.tracks=%s', len(media.tracks), len(media.children), len(metadata.tracks) )
      valid_keys = []
      for track in media.children:
        guid = track.guid
        valid_keys.append(guid)
        meta_track = metadata.tracks[guid]
        meta_track.title = track.title
        meta_track.rating_count = 0
        #meta_track.rating = float(0) #doesn't work
        meta_track.summary = BLANK_FIELD
        ftitle = fuzzy(track.title)
        
        if ftitle in nfo_tracks:
          nfo_track = nfo_tracks[ftitle]
          if nfo_track and meta_track:
            if 'rating' in nfo_track: 
              meta_track.rating_count = nfo_track['rating']
              #meta_track.rating = float((meta_track.rating_count + 19) / 20) #doesn't work
            if 'review' in nfo_track: meta_track.summary = nfo_track['review']
            # meta_track.track_index = track.index
            # meta_track.disc_index = nfo_track['disc']
      metadata.tracks.validate_keys(valid_keys)

    Log("finished album nfo import")

def LogDict(dic, title=''):
  try:
    s = '--'.join('{} : {}'.format(key, value) for key, value in dic.iteritems())
    s = 'LogDict:%s =\n%s' % (title, s)
    Log(s)
  except Exception as e:
    Log('error get_dict = %s', e)
    pass

def LogObj(obj, title=''):
  try:
    s = 'logObj:%s =\n%s' % (title, inspect.getmembers(obj))
    s = s.replace("), (", "), \n(")
    s = s.replace("', '","', \n'")
    s = s.replace("', {'", "', {\n'")
    Log(s)
  except Exception as e:
    Log('error LogObj = %s', e)
    pass
