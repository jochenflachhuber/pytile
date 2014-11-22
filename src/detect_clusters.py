import numpy as np
import cv2
import os
from math import sin, pi, sqrt

def count(image):
    contours,l = fetch_contours(image,100)
    return len(contours)

def fetch_contours(image, min_length):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    val_channel = hsv[:,:,2]
    retv, val_mask = cv2.threshold(val_channel,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    #apply closing in order to remove 'holes' in our tiles
    kernel = np.ones((7,7),np.uint8) #the kernel size has to be adapted if we use smaller samples
    closed_enough = cv2.morphologyEx(val_mask, cv2.MORPH_CLOSE, kernel)
    """
    Find contours in each candidate region.
    We use RETR_EXTERNAL because we're not interested in inner sub-regions
    """
    contours, hier = cv2.findContours(closed_enough,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    """
    Avoid counting contours that surely don't belong to a tile.
    I noticed a value channel based approach is sensible to noise and creates many 0 length contours.
    This explains the condition in the returned list:
    at the resolution we're working at a tile contour should be certainly larger than 100 pixels.
    """
    candidate_contours = np.array([contour for contour in contours if cv2.arcLength(contour,True) > min_length])
    #it may be a good idea to return an array of lengths to induce other contour properties later
    candidate_contours_lengths = np.array([cv2.arcLength(candidate, True) for candidate in candidate_contours])
    return candidate_contours, candidate_contours_lengths

def get_winning_tile(contours,lengths):
    winning_tile_index = np.argmin(lengths)
    return contours[winning_tile_index]

def is_somewhat_straight(angle,tolerance):
    #all quantities in degrees
    #use sin(2x) because it's 0 every 90 deg
    return abs(sin(pi/90*angle)) < sin(pi/90*tolerance)

def straighten(image,angle,tolerance=4,crop=True):
    """
    Rotate melds that are not orthogonal within the tolerance(degrees)
    The default behaviour doesn't resize the canvas accordingly to the angle of 
    rotation. If the fourth argument is set to True, the canvas is enlarged to 
    make the rotated image fit completely.
    
    This is done by taking the LARGEST canvas containing any rotation of the 
    source image, i.e. a square with edge length equal to the source's diagonal.
    This could be memory expensive for small angles but not a big deal with the
    kind of images this procedure is supposed to work with (roughly 100px tall).
    A more fine solution could be providing something like the following:
        dst_height = src_width*cos(90-angle) + src_heigth*cos(angle)
        dst_width = src_width*cos(angle) + src_heigth*cos(90-angle)
    with proper attention to the angle range and source's image ratio, applying 
    basic trigonometry.
    Nonetheless the current conservative approach is ok, imo.
        
    """
    if is_somewhat_straight(angle,tolerance):
        return image
    else:
        rows,cols,channels = image.shape
        if crop:         
            dst = image
            dst_rows,dst_cols,dst_channels = dst.shape
        else:
            diagonal = int(sqrt(rows*rows + cols*cols))
            offsetX = (diagonal - cols)/2
            offsetY = (diagonal - rows)/2
            dst = np.zeros((diagonal,diagonal,channels),dtype=np.uint8)
            #compute the center of rotation for the newly created canvas
            dst_rows,dst_cols,dst_channel = dst.shape             
            #correctly positioning the old image in the new canvas
            dst[offsetY:rows+offsetY,offsetX:cols+offsetX,:] = image
            
        rot_matrix = cv2.getRotationMatrix2D((dst_cols/2,dst_rows/2),angle,1.0)            
        rotated = cv2.warpAffine(dst,rot_matrix,(dst_cols,dst_rows))
        return rotated



if __name__ == '__main__':
    for sample_index in range(1,8):
        image = cv2.imread('test/test_data/test_00{}.jpg'.format(sample_index))
        contours, lengths = fetch_contours(image,100) #min_length should be tuned on image size
        if contours.size == 0:
            break #you know, this really shouldn't happen
        segment_index = 1
        #we build the file name this way
        test_data_path = 'test/test_data/'
        melds_dir = 'melds_00{}'.format(sample_index)
        #the winning tile *should* be the only one alone if the hand makes any sense
        winning_tile_index = np.argmin(lengths)
        #for each sample create a folder with the melds (ROI) sub-images
        if not os.path.exists(test_data_path + melds_dir): #let's be error proof, kinda
            os.makedirs(test_data_path + melds_dir)
        #for each contour enclosing the ROI...
        for contour_index in range(len(contours)):
            (x,y,w,h) = cv2.boundingRect(contours[contour_index]) #bound it with a rectangle
            #while searching for the minimum enclosing rectangle, which is not
            #in general aligned with our margins
            rotated_box = cv2.minAreaRect(contours[contour_index])
            #rotated_box: Box2D structure - ( top-left corner(x,y), (width, height), clockwise angle of rotation )
            bounded_meld = image[y:y+h,x:x+w] #this is the ROI in the boundingRect
            """
            the winning tile usually lays on its major side, that's why it has to be rotated
            an extra 90 deg besides the straightening
            """
            if contour_index != winning_tile_index:
                segment_out = straighten(bounded_meld,rotated_box[2]) #just check if not orthogonal
                cv2.imwrite(test_data_path + melds_dir + '/segment_{}.jpg'.format(segment_index), segment_out)
            else:
                segment_out = straighten(bounded_meld,rotated_box[2])
                #the winning tile is usually horizontal, must rotate it 90 degrees
                segment_out = straighten(segment_out,-90,0,False)
                cv2.imwrite(test_data_path + melds_dir + '/single_segment_{}.jpg'.format(segment_index), segment_out)
            segment_index += 1
