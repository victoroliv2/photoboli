symbolic/convert -resize $3x$3 $1 $2 
symbolic/mogrify $2
~/Image-ExifTool-11.06/exiftool -TagsFromFile $1 $2
~/Image-ExifTool-11.06/exiftool -Orientation=1 -n $2
rm -fv $2*original*
