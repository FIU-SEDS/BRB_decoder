import folium
from folium import plugins
import matplotlib.pyplot as plt
import base64
from io import BytesIO
import os

kml = input("Give me the name of the KML file (same directory): ")
kmlpre = [kml[:kml.find('.')]][0]

with open(kml, 'r') as file:
    raw = file.read()

marker1 = 'BRBDATA'
index1  = raw.find(marker1)
if index1 == -1:
    print("BRB byte data header not found. This file does not look like a BRB data file.")
    quit()
else:
    raw = raw[index1 + len(marker1) + 1:]

marker2 = '-->'
index2 = raw.find(marker2)
if index2 == -1:
    print("BRB byte data header not found. This file does not look like a BRB data file.")
    quit()
else:
    raw = raw[:index2 - 1]

unprocessed = open(kmlpre + '_unprocessed.txt', 'w').close()
unprocessed = open(kmlpre + '_unprocessed.txt', 'a')
unprocessed.write(raw)
unprocessed.close()

with open(kmlpre + '_unprocessed.txt', 'r') as file:
    unprocessed = file.read()

BRBbytes = unprocessed.strip().split()
for i in range(len(BRBbytes)):
    if BRBbytes[i] != '5A':
        BRBbytes = BRBbytes[i:]
        break
BRBbytes = [byte for byte in BRBbytes if byte.upper() != 'FF']
BRBbytes.reverse()
for i in range(len(BRBbytes)):
    if BRBbytes[i] != '5A':
        BRBbytes = BRBbytes[i:]
        break
BRBbytes.reverse()

mark = hex(int(input("What is the nearest, whole degree of latitude (no negatives) you launched from? ")))[2:].upper()
databytes = []

locations  = []
for i in range(len(BRBbytes)):
    if BRBbytes[i] == '50':
        locations.append(i)
databytes = BRBbytes[locations[0]:]

if (len(databytes)%15 == 0):
    print("The recorded number of bytes is 15 for all data frames.")
else:
    print("The recorded number of bytes does not correspond to 15 byte data frames. Please look for data frame pattern and delete excessive data (often 5A and FF bytes).")
    processed = open(kmlpre + '_bytes.txt', 'w').close()
    processed = open(kmlpre + '_bytes.txt', 'a')
    for i in range(len(databytes)):
        for j in range(15):
            processed.write(databytes[i*15+j] + " ")
        processed.write("\n")
    processed.close()
    quit()

lines = int(len(databytes)/15)
processed = open(kmlpre + '_bytes.txt', 'w').close()
processed = open(kmlpre + '_bytes.txt', 'a')
for i in range(lines - 1):
    for j in range(14):
        processed.write(databytes[i*15 + j] + " ")
    processed.write(databytes[i*15 + 14])
    processed.write("\n")
for j in range(14):
    processed.write(databytes[(lines-1)*15 + j] + " ")
processed.write(databytes[(lines-1)*15 + 14])
processed.close()

#Strip and split data slices correctly
data = open(kmlpre + '_data.txt', 'w').close()
data = open(kmlpre + '_data.txt', 'a')

with open(kmlpre + '_bytes.txt', 'r') as file:
    processed = file.read()
slices = processed.split("\n")

print("Converting hex to encoded data...")
#Data frame format: Longitude (6 decimal, degree representation), latitude (6 decimal, degree representation), altitude in feet?, number of satellites, time in UTC
for slise in slices:
    byteslice = slise.split(" ")
    longdec = int(byteslice[1],16)*10000 + int(byteslice[2],16)*100 + int(byteslice[3],16)
    longnum = -(int(byteslice[0],16) + longdec/600000)
    longitude = f"{longnum:.6f}"
    latdec = int(byteslice[5],16)*10000 + int(byteslice[6],16)*100 + int(byteslice[7],16)
    latnum = (int(byteslice[4],16) + latdec/600000)
    latitude = f"{latnum:.6f}"
    altstr = str(int(byteslice[8],16)*10000 + int(byteslice[9],16)*100 + int(byteslice[10],16))
    sat = str(int(byteslice[11],16))
    hours = str(int(byteslice[12],16))
    minutes = str(int(byteslice[13],16))
    seconds = str(int(byteslice[14],16))
    data_n = f"{latitude}, {longitude}, altitude (ft): {altstr}, sats: {sat}, UTC {hours:02}:{minutes:02}:{seconds:02}"
    data.write(data_n)
    data.write("\n")
data.close()

# Helper to convert matplotlib RGBA to hex
def matplotlib_color_to_hex(rgba):
    r, g, b, _ = [int(255 * x) for x in rgba]
    return f"#{r:02x}{g:02x}{b:02x}"


#Read GPS + altitude data
gps_points = []
altitudes = []

print("Converting data to GIS format...")
with open(kmlpre + '_data.txt', 'r') as f:
    for line in f:
        if line.strip() == '':
            continue
        parts = line.strip().split(',')
        lat = float(parts[0])
        lon = float(parts[1])
        alt = int(parts[2].split(':')[1].strip())
        gps_points.append((lat, lon))
        altitudes.append(alt)

#Normalize altitude for colormap
norm = plt.Normalize(min(altitudes), max(altitudes))
cmap = plt.get_cmap('plasma')

print("Creating map tiling...")
#Create the folium map
m = folium.Map(
    location=gps_points[0], zoom_start=18,
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri Satellite'
)

print("Drawing rocket trajectory...")
#Draw colored path
for i in range(len(gps_points) - 1):
    point1 = gps_points[i]
    point2 = gps_points[i + 1]
    alt = altitudes[i]
    color = matplotlib_color_to_hex(cmap(norm(alt)))
    folium.PolyLine([point1, point2], color=color, weight=5, opacity=0.9).add_to(m)

print("Adding formating rules and saving...")
#Draw colored path by altitude
for i in range(len(gps_points) - 1):
    point1 = gps_points[i]
    point2 = gps_points[i + 1]
    alt = altitudes[i]
    color = matplotlib_color_to_hex(cmap(norm(alt)))
    folium.PolyLine([point1, point2], color=color, weight=5, opacity=0.9).add_to(m)

#Create colorbar PNG image in memory
fig, ax = plt.subplots(figsize=(2.0, 4.0))
cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=ax)
cb.set_label('Altitude (ft)')
fig, ax = plt.subplots(figsize=(2.0, 4.0))
cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=ax)
cb.set_label('Altitude (ft)')

img_data = BytesIO()
plt.savefig(img_data, format='png', bbox_inches='tight', dpi=100)
img_data.seek(0)
encoded = base64.b64encode(img_data.read()).decode('utf-8')

#Overlay colorbar on the folium map as HTML
colorbar_html = f'''
<div style="position: fixed; 
     bottom: 30px; left: 30px; width: 60px; height: 260px; 
     background-color: white; border:2px solid grey; z-index:9999;
     padding: 5px;">
    <img src="data:image/png;base64,{encoded}" style="width: 100%; height: 100%;">
</div>
'''

m.get_root().html.add_child(folium.Element(colorbar_html))

#Save final map
filename = kmlpre + "_map.html"
m.save(filename)
print("Map with colorbar saved as '" + kmlpre + "_map.html'")

os.remove(kmlpre + '_unprocessed.txt')