"""

Features found we could explore :

Computation of the whites in the picture with the histogramme + if above 175 then more chances to be full (maybe extra full)

Use the same logic for the mean of their color : above 25 then probably dirty, less than 20 then probably clean


Features we don't think we should use :
- file_size, image_width, image_height : After study, it does not seem that this parameter is useful. Moreover, in the real project, it would lead to problems since the same camera will be used for every bin. So every file will be of the same size, heigh and width



"""