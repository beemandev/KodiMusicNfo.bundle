import os, string, re, unicodedata, sys, urllib, urlparse

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
  
def FindArtistNfo(metadata, paths):
  for path in paths:
    for f in os.listdir(path):
      (fn, ext) = os.path.splitext(f)
      if(fn == 'artist' and not fn.startswith('.') and ext[1:] == "nfo"):
        nfo_file = os.path.join(path, f)
        nfo_text = Core.storage.load(nfo_file)
        # work around failing XML parses for things with &'s in them. This may need to go farther than just &'s....
        nfo_text = NFO_TEXT_REGEX_1.sub('&amp;', nfo_text)
        # remove empty xml tags from nfo
        Log('Removing empty XML tags from artist.nfo...')
        nfo_text = NFO_TEXT_REGEX_2.sub('', nfo_text)

        nfo_text_lower = nfo_text.lower()
        if nfo_text_lower.count('<artist') > 0 and nfo_text_lower.count('</artist>') > 0:
            # Remove URLs (or other stuff) at the end of the XML file
            nfo_text = '{content}</artist>'.format(content=nfo_text.rsplit('</artist>', 1)[0])

            # likely a kodi nfo file
            try:
                nfo_xml = XML.ElementFromString(nfo_text).xpath('//artist')[0]
            except:
                Log('ERROR: Cant parse XML in {nfo} Skipping!'.format(nfo=nfo_file))
                continue

            # remove empty xml tags
            Log('Removing empty XML tags from artist.nfo...')
            nfo_xml = remove_empty_tags(nfo_xml)

            add_tag(nfo_xml, metadata.summary, 'biography')
            add_tags(nfo_xml, metadata.genres, 'genre')
            add_tags(nfo_xml, metadata.styles, 'style')
            add_tags(nfo_xml, metadata.moods, 'mood')
    
        Log("artist fields loaded from file %s", nfo_file)

def FindAlbumNfo(metadata, paths):
  for path in paths:
    for f in os.listdir(path):
      (fn, ext) = os.path.splitext(f)
      if(fn == 'album' and not fn.startswith('.') and ext[1:] == "nfo"):
        nfo_file = os.path.join(path, f)
        nfo_text = Core.storage.load(nfo_file)
        # work around failing XML parses for things with &'s in them. This may need to go farther than just &'s....
        nfo_text = NFO_TEXT_REGEX_1.sub('&amp;', nfo_text)
        # remove empty xml tags from nfo
        Log('Removing empty XML tags from album.nfo...')
        nfo_text = NFO_TEXT_REGEX_2.sub('', nfo_text)

        nfo_text_lower = nfo_text.lower()
        if nfo_text_lower.count('<album') > 0 and nfo_text_lower.count('</album>') > 0:
            # Remove URLs (or other stuff) at the end of the XML file
            nfo_text = '{content}</album>'.format(content=nfo_text.rsplit('</album>', 1)[0])

            # likely a kodi nfo file
            try:
                nfo_xml = XML.ElementFromString(nfo_text).xpath('//album')[0]
            except:
                Log('ERROR: Cant parse XML in {nfo} Skipping!'.format(nfo=nfo_file))
                continue

            # remove empty xml tags
            Log('Removing empty XML tags from album.nfo...')
            nfo_xml = remove_empty_tags(nfo_xml)

            add_tag(nfo_xml, metadata.summary, 'review')
            add_tag(nfo_xml, metadata.studio, 'label')
            add_tags(nfo_xml, metadata.genres, 'genre')
            add_tags(nfo_xml, metadata.styles, 'style')
            add_tags(nfo_xml, metadata.moods, 'mood')

        Log("album fields loaded from file %s", nfo_file)

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
    Log('Empty XMLTags removed: {number} {tags}'.format(
        number=len(empty_tags) or None,
        tags=sorted(set(empty_tags)) or ''
    ))
    return document

def add_tag(nfo_xml, metadata_tag, name):
    try:
        metadata_tag = nfo_xml.xpath(name)[0].text
    except:
        Log('No <{tag}> tag in nfo'.format(tag=name))
        pass

def add_tags(nfo_xml, metadata_tags, name):
    try:
        tags = nfo_xml.xpath(name)
        metadata_tags.clear()
        [metadata_tags.add(t.strip()) for tagXML in tags for t in tagXML.text.split('/')]
    except:
        Log('No <{tag}> tag in nfo'.format(tag=name))
        pass


class KodiArtistNfo(Agent.Artist):
  contributes_to = ['com.plexapp.agents.discogs', 'com.plexapp.agents.lastfm', 'com.plexapp.agents.plexmusic', 'com.plexapp.agents.none']
  primary_provider = False
  persist_stored_files = False
  name = "Kodi Nfo (Artists)"
  
  def search(self, results, media, lang):
    results.Append(MetadataSearchResult(id = 'null', name=media.artist, score = 100))
    
  def update(self, metadata, media, lang, child_guid=None):
    Log(metadata.summary)
    dirs = {}
    
    for a in media.albums:
      for t in media.albums[a].tracks:
        track = media.albums[a].tracks[t].items[0]
        dirs[os.path.dirname(track.parts[0].file)] = True
    
    artist_dirs = GetParentDir(dirs)
    ## Assumes folder structure of
    #     * Artist
    #         * summary.txt
    #         * Album
    #           * summary.txt
    #           * audio tracks
    #     ... etc.
    
    #Log(artist_dir) #debug
    
    FindArtistNfo(metadata, artist_dirs) #searches for artist.nfo in Artist folder and adds fields to the metadata
    
    Log("finished")
    
    
    
    
class KodiAlbumNfo(Agent.Album):
  name = "Kodi Nfo (Albums)"
  primary_provider = False
  persist_stored_files = False
  contributes_to = ['com.plexapp.agents.discogs', 'com.plexapp.agents.lastfm', 'com.plexapp.agents.plexmusic', 'com.plexapp.agents.none']
  
  def search(self, results, media, lang):
    results.Append(MetadataSearchResult(id = 'null', score = 100))
    
  def update(self, metadata, media, lang):
    #metadata.summary = " " #this is the only way I've found to blank it out if the summary file is removed, empty string doesn't work
    dirs = {}
    
    for t in media.tracks:
        track = media.tracks[t].items[0]
        #file path of the track is: track.parts[0].file
        dirs[os.path.dirname(track.parts[0].file)] = True
    
    FindAlbumNfo(metadata, dirs) #searches for album.nfo in Album folder and adds fields to the metadata
    
    Log("finished")


    