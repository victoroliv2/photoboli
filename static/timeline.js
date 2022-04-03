function set_map(elem) {
    $('#map').empty();

    var features = [];
	var center_lat = elem[0]["lat"];
	var center_lon = elem[0]["lon"];
	var counter = 0;

    for (var p in elem) {
        var lat = elem[p]["lat"];
        var lon = elem[p]["lon"];
        var loc = new ol.Feature({ geometry: new ol.geom.Point(ol.proj.fromLonLat([lon, lat])) });
        loc.setStyle(new ol.style.Style({
            image: new ol.style.Icon(/** @type {olx.style.IconOptions} */ ({
            //color: [113, 140, 0],
            crossOrigin: 'anonymous',
            //src: 'https://openlayers.org/en/v4.6.5/examples/data/dot.png'
            src: 'thumbs/100/' + elem[p]["filename"]
            }))
        }));
        features.push(loc);
    }

    var vectorSource = new ol.source.Vector({ features: features });
    var vectorLayer = new ol.layer.Vector({ source: vectorSource });

    var rasterLayer = new ol.layer.Tile({
      source: new ol.source.TileJSON({
        url: 'https://api.tiles.mapbox.com/v3/mapbox.geography-class.json?secure',
        crossOrigin: ''
      })
    });

    var map = new ol.Map({
      layers: [rasterLayer, vectorLayer],
      target: document.getElementById('map'),
      view: new ol.View({
        center: ol.proj.fromLonLat([center_lon, center_lat]),
        zoom: 4 // TODO: compute zoom from pic distance
      })
    });
}

function set_faces(faces) {
    $('#people').empty();

    for (var index in faces) {
        var img = document.createElement("img");
        img.src = faces[index];
        img.class = "img-rounded";
        // TODO: generate 64x64 face thumbs directly
        img.style.height = '64px';
        img.style.width  = '64px';

        var ppl = document.getElementById("people");
        ppl.appendChild(img);
    }
}

var current_full_photo = null;
var next_hashes = {};
var prev_hashes = {};
var pig_objs = [];
var y_click = 0;

function clear_timeline() {
    current_full_photo = null;
    next_hashes = {};
    prev_hashes = {};
    pig_objs = [];
	y_click = 0;
}

function back_full_photo(filename) {
    $('#full_photo').css('display', 'none');
    $('#timeline')  .css('display', 'inline');

    for (var p in pig_objs) {
        pig_objs[p].enable();
    }

	window.scrollTo(0, y_click);
}

function set_full_photo(filename) {    
    for (var p in pig_objs) {
        pig_objs[p].disable();
    }

    $('#full_photo').css('display', 'inline');
    $('#timeline')  .css('display', 'none');

    document.getElementById('photo').src = 'thumbs/2000/' + filename;

    current_full_photo = filename;

    $.ajax({
        type: 'get',
        url: 'cgi/photo/' + filename,
        success: function (data) {
        	console.log(data);
			$('#metadata_date').text(data["date"]);
        }
    });

    // TODO: face detection support
    $.ajax({
        type: 'get',
        url: 'cgi/faces/' + filename,
        success: function (data) {
        console.log(data);
        set_faces(data);
        }
    });

    // TODO: show map with nearby photos?
    // $.ajax({
    //     type: 'get',
    //     url: 'cgi/nearby/' + filename,
    //     success: function (data) {
    //     console.log(data);
    //     //set_map(data);
    //     }
    // });
}

function timeline_get_next() {
    if (current_full_photo in next_hashes) { return next_hashes[current_full_photo]; }
    else return null;
}

function timeline_get_prev() {
    if (current_full_photo in prev_hashes) { return prev_hashes[current_full_photo]; }
    else return null;
}

function timeline_gen(data) {
    var imageData = data;

    for (var p in pig_objs) {
        pig_objs[p].disable();
    }

    clear_timeline();
    $('#pig').empty();
 
    var counter = 0;

    var prev_hash = null;

    for (var k in imageData["data"]) {
        var elem = imageData["data"][k];
        if (Array.isArray (elem)) {

            for (var e in elem) {
                var cur_hash = elem[e]["filename"];
                if (prev_hash) { 
                    next_hashes[prev_hash] = cur_hash;
                    prev_hashes[cur_hash] = prev_hash;
                }
                prev_hash = cur_hash;
            }

            var cID = 'pig' + counter.toString();

            var div = document.createElement('div');
            div.id = cID;
            document.getElementById('pig').appendChild(div);

            var pig = new Pig(elem, {
                containerId: cID,
                urlForSize: function(filename, size) {
                return 'thumbs/' + size + '/' + filename;
                },
                handleClick: function(off, filename) {
					y_click = off;
                    set_full_photo(filename);
                }
            }).enable();

            pig_objs.push(pig);

            counter++;
        }
        else {
            if ('year' in elem) {
                htype = 'h1';
                htext = elem.year;
            }
            else if ('month' in elem) {
                htype = 'h2';
                month_names = { 1 : "January",
                                2 : "February",
                                3: "March",
                                4:  "April",
                                5:  "May",
                                6:  "June",
                                7:  "July",
                                8:  "August",
                                9:  "September",
                                10: "October",
                                11: "November",
                                12: "December"};
                htext = month_names[elem.month];
            }
            else if ('region' in elem) {
                htype = 'h3';
                htext = elem.region;
            }
            else if ('cities' in elem) {
                htype = 'h4';
                htext = elem.cities;
            }
            else {
                continue;
            }

            var newParagraph = document.createElement(htype);
            newParagraph.textContent = htext;
            document.getElementById('pig').appendChild(newParagraph);
        }
   }
}
