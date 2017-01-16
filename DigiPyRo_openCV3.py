# DigiPyRo is a program with two main functions:
# 1. Digital rotation of movies.
# 2. Single-particle tracking.
# All of its functionalities can be accessed through the GUI window which appears when DigiPyRo is run.
# See the README and instructables for further documentation, installation instructions and examples.


# Import necessary Python modules
import cv2
import numpy as np
from Tkinter import *
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import scipy as sp
from scipy.optimize import leastsq
import time


########################
### Helper Functions ###
########################

## Helper Functions: Section 1 -- User-Interaction Functions
## The majority of functions in this section relate to user-identification of the region of interest (ROI) which will be digitally rotated,
## or the intialization of single-particle tracking

# Allows user to manually identify center of rotation
def centerClick(event, x, y, flags, param):
    global center, frame			# declare these variables as global so that they can be used by various functions without being passed explicitly
    clone = frame.copy()			# save the original frame
    if event == cv2.EVENT_LBUTTONDOWN:		# if user clicks 
        center = (x,y)				# set click location as center
        cv2.circle(frame, (x,y), 4, (255,0,0), -1) # draw circle at center
        cv2.imshow('CenterClick', frame)	# show updated image
        frame = clone.copy() 			# resets to original image so that if the user reselects the center, the old circle will not appear

# Shifts image so that it is centered at (x_c, y_c)
def centerImg(img, x_c, y_c):
    dx = (width/2) - x_c
    dy = (height/2) - y_c
    shiftMatrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, shiftMatrix, (width, height))

# User drags mouse and releases to indicate a conversion factor between pixels and units of distance
def unitConversion(event, x, y, flags, param):
    global frame, uStart, uEnd, unitCount, unitType, unitConv
    clone = frame.copy()
    if event == cv2.EVENT_LBUTTONDOWN:
        uStart = (x,y)
    elif event == cv2.EVENT_LBUTTONUP:
        uEnd = (x,y)
        d2 = ((uEnd[0] - uStart[0])**2) + ((uEnd[1] - uStart[1])**2)
        pixelLength = (d2**(0.5))/2
        unitConv = unitCount / pixelLength
        cv2.line(frame, uStart, uEnd, (255,0,0), 1)
        cv2.imshow('Distance Calibration', frame)
        frame = clone.copy()

# User drags mouse and releases along a diameter of the particle to set an approximate size and location of particle for DPR to search for
def locate(event, x, y, flags, param):
    global frame, particleStart, particleEnd, particleCenter, particleRadius	# declare these variables as global so that they can be used by various functions without being passed explicitly
    clone = frame.copy()							# save the original frame
    if event == cv2.EVENT_LBUTTONDOWN:						# if user clicks
        particleStart = (x,y)							# record location
    elif event == cv2.EVENT_LBUTTONUP:						# if user releases click
        particleEnd = (x,y)							# record location
        particleCenter = ((particleEnd[0] + particleStart[0])/2, (particleEnd[1] + particleStart[1])/2)  # define the center as the midpoint between start and end points
        d2 = ((particleEnd[0] - particleStart[0])**2) + ((particleEnd[1] - particleStart[1])**2)
        particleRadius = (d2**(0.5))/2
        cv2.circle(frame, particleCenter, int(particleRadius+0.5), (255,0,0), 1)	# draw circle that shows the radius and location of cirlces that the Hough circle transform will search for
        cv2.imshow('Locate Ball', frame)					  	# show updated image
        frame = clone.copy() 								# resets to original image

# User clicks points along the circumference of a circular ROI. This function records the points and calculates the best-fit circle through the points.
def circumferencePoints(event, x, y, flags, param):
    global npts, center, frame, xpoints, ypoints, r, poly1, poly2		# declare these variables as global so that they can be used by various functions without being passed explicitly
    if event == cv2.EVENT_LBUTTONDOWN:						# if user clicks
        if (npts == 0):								# if this is the first point, intialize the arrays of x-y coords
            xpoints = np.array([x])
            ypoints = np.array([y])
        else:									# otherwise, append the points to the arrays
            xpoints = np.append(xpoints,x)
            ypoints = np.append(ypoints,y)
        npts+=1
        cv2.circle(frame, (x,y), 3, (0,255,0), -1)
        clone = frame.copy()
        if (len(xpoints) > 2):							# if there are more than 2 points, calculate the best-fit circle through the points
            bestfit = calc_center(xpoints, ypoints)
            center = (bestfit[0], bestfit[1])
            r = bestfit[2]
            poly1 = np.array([[0,0],[frame.shape[1],0],[frame.shape[1],frame.shape[0]], [0,frame.shape[0]]])
            poly2 = np.array([[bestfit[0]+r,bestfit[1]]])
            circpts = 100
            for i in range(1,circpts):						# approximate the circle as a 100-gon (which makes it easier to draw the mask, as we define the mask region as the area between two polygons)
                theta =  2*np.pi*(float(i)/circpts)
                nextpt = np.array([[int(bestfit[0]+(r*np.cos(theta))),int(bestfit[1]+(r*np.sin(theta)))]])
                poly2 = np.append(poly2,nextpt,axis=0)
            cv2.circle(frame, center, 4, (255,0,0), -1)
            cv2.circle(frame, center, r, (0,255,0), 1)
        cv2.imshow('CenterClick', frame) 
        frame = clone.copy()
        
# The same as "circumferencePoints", except this calculates a polygon ROI. The center is calculated as the "center of mass" of the polygon
def nGon(event, x, y, flags, param):
    global npts, center, frame, xpoints, ypoints, r, poly1, poly2 		# declare these variables as global so that they can be used by various functions without being passed explicitly
    if event == cv2.EVENT_LBUTTONDOWN:						# if user clicks
        if (npts == 0):
            xpoints = np.array([x])
            ypoints = np.array([y])
        else:
            xpoints = np.append(xpoints,x)
            ypoints = np.append(ypoints,y)
        npts+=1
        cv2.circle(frame, (x,y), 3, (0,255,0), -1)
        clone = frame.copy()
        if (len(xpoints) > 2):
            center = (int(np.sum(xpoints)/npts), int(np.sum(ypoints)/npts))
            poly1 = np.array([[0,0],[frame.shape[1],0],[frame.shape[1],frame.shape[0]], [0,frame.shape[0]]])
            poly2 = np.array([[xpoints[0],ypoints[0]]])
            for i in range(len(xpoints)-1):
                nextpt = np.array([[xpoints[i+1], ypoints[i+1]]])
                poly2 = np.append(poly2,nextpt,axis=0)
                cv2.line(frame, (xpoints[i], ypoints[i]), (xpoints[i+1], ypoints[i+1]), (0, 255, 0), 1)
            cv2.line(frame, (xpoints[len(xpoints)-1], ypoints[len(xpoints)-1]), (xpoints[0],ypoints[0]), (0, 255, 0), 1)       
            cv2.circle(frame, center, 4, (255,0,0), -1)
        cv2.imshow('CenterClick', frame) 
        frame = clone.copy()

# Removes the most recently clicked point in the array of circle/polygon circumference points. 
def removePoint(orig):
    global npts, center, frame, xpoints, ypoints, r, poly1, poly2, custMask
    if npts == 0:
        return

    else:
        npts -= 1
        if npts == 0:
            xpoints = np.empty(0)
            ypoints = np.empty(0)
        elif npts == 1:
            xpoints = np.array([xpoints[0]])
            ypoints = np.array([ypoints[0]])
        else:
            xpoints = xpoints[0:npts]
            ypoints = ypoints[0:npts]

    frame = orig.copy()
    for i in range(len(xpoints)):
        cv2.circle(frame, (xpoints[i], ypoints[i]), 3, (0,255,0), -1)
    if (len(xpoints) > 2):							# if there are more than 2 points after removing the most recent point, recalculate the center of rotation and the mask region
        if custMask:
            poly1 = np.array([[0,0],[frame.shape[1],0],[frame.shape[1],frame.shape[0]], [0,frame.shape[0]]])
            poly2 = np.array([[xpoints[0],ypoints[0]]])
            for i in range(len(xpoints)-1):
                nextpt = np.array([[xpoints[i+1], ypoints[i+1]]])
                poly2 = np.append(poly2,nextpt,axis=0)
                cv2.line(frame, (xpoints[i], ypoints[i]), (xpoints[i+1], ypoints[i+1]), (0, 255, 0), 1)
            cv2.line(frame, (xpoints[len(xpoints)-1], ypoints[len(xpoints)-1]), (xpoints[0],ypoints[0]), (0, 255, 0), 1)
            cv2.circle(frame, center, 4, (255,0,0), -1)
        else:
            bestfit = calc_center(xpoints, ypoints)
            center = (bestfit[0], bestfit[1])
            r = bestfit[2]
            poly1 = np.array([[0,0],[frame.shape[1],0],[frame.shape[1],frame.shape[0]], [0,frame.shape[0]]])
            poly2 = np.array([[bestfit[0]+r,bestfit[1]]])
            circpts = 100
            for i in range(1,circpts):
                theta =  2*np.pi*(float(i)/circpts)
                nextpt = np.array([[int(bestfit[0]+(r*np.cos(theta))),int(bestfit[1]+(r*np.sin(theta)))]])
                poly2 = np.append(poly2,nextpt,axis=0)
            cv2.circle(frame, center, 4, (255,0,0), -1)
            cv2.circle(frame, center, r, (0,255,0), 1)
        cv2.imshow('CenterClick', frame)

# Calculates the center and radius of the best-fit circle through an array of points (by least-squares method)
def calc_center(xp, yp):
    n = len(xp)
    circleMatrix = np.matrix([[np.sum(xp**2), np.sum(xp*yp), np.sum(xp)], [np.sum(xp*yp), np.sum(yp**2), np.sum(yp)], [np.sum(xp), np.sum(yp), n]])
    circleVec = np.transpose(np.array([np.sum(xp*((xp**2)+(yp**2))), np.sum(yp*((xp**2)+(yp**2))), np.sum((xp**2)+(yp**2))]))
    ABC = np.transpose(np.dot(np.linalg.inv(circleMatrix), circleVec))
    xc = ABC.item(0)/2
    yc = ABC.item(1)/2
    a = ABC.item(0)
    b = ABC.item(1)
    c = ABC.item(2)
    d = (4*c)+(a**2)+(b**2)
    diam = d**(0.5)
    return np.array([int(xc), int(yc), int(diam/2)])

# Adds diagnostic information, including time and physical/digital rotations to each frame of the movie
def annotateImg(img, i):
    font = cv2.FONT_HERSHEY_TRIPLEX

    dpro = 'DigiPyRo'
    dproLoc = (25, 50)
    cv2.putText(img, dpro, dproLoc, font, 1, (255, 255, 255), 1)
    
    img[25:25+spinlab.shape[0], (width-25)-spinlab.shape[1]:width-25] = spinlab

    timestamp = 'Time: ' + str(round((i/fps),1)) + ' s'
    tLoc = (width - 225, height-25)
    cv2.putText(img, timestamp, tLoc, font, 1, (255, 255, 255), 1)

    crpm = 'Original Rotation of Camera: '
    crpm += str(camRPM) + 'RPM'
    
    drpm = 'Additional Digital Rotation: '
    if (digiRPM > 0):
        drpm += '+'
    drpm += str(digiRPM) + 'RPM'

    cLoc = (25, height - 25)
    dLoc = (25, height - 65)
    cv2.putText(img, drpm, dLoc, font, 1, (255, 255, 255), 1)
    cv2.putText(img, crpm, cLoc, font, 1, (255, 255, 255), 1)

# Displays instructions on the screen for identifying the circle/polygon of interest
def instructsCenter(img):
    font = cv2.FONT_HERSHEY_PLAIN
    line1 = 'Click on 3 or more points along the border of the circle or polygon'
    line1Loc = (25, 50)
    line2 = 'around which the movie will be rotated.'
    line2Loc = (25, 75)
    line3 = 'Press the BACKSPACE or DELETE button to undo a point.'
    line3Loc = (25,100)
    line4 = 'Press ENTER when done.'
    line4Loc = (25,125) 
    
    cv2.putText(img, line1, line1Loc, font, 1, (255, 255, 255), 1)
    cv2.putText(img, line2, line2Loc, font, 1, (255, 255, 255), 1)
    cv2.putText(img, line3, line3Loc, font, 1, (255, 255, 255), 1)
    cv2.putText(img, line4, line4Loc, font, 1, (255, 255, 255), 1)

# Displays instructions for drawing a circle around the ball.
def instructsBall(img):
    font = cv2.FONT_HERSHEY_PLAIN
    line1 = 'Click and drag to create a circle around the ball.'
    line1Loc = (25, 50)
    line2 = 'The more accurately the initial location and size of the ball'
    line2Loc = (25, 75)
    line3 = 'are matched, the better the tracking results will be.'
    line3Loc = (25, 100)
    line4 = 'Press ENTER when done.'
    line4Loc = (25, 125)

    cv2.putText(img, line1, line1Loc, font, 1, (255, 255, 255), 1)
    cv2.putText(img, line2, line2Loc, font, 1, (255, 255, 255), 1)
    cv2.putText(img, line3, line3Loc, font, 1, (255, 255, 255), 1)
    cv2.putText(img, line4, line4Loc, font, 1, (255, 255, 255), 1)

# Displays instructions for drawing a line for unit conversion
def instructsUnit(img):
    font = cv2.FONT_HERSHEY_PLAIN
    line1 = 'Click and release to draw a line of'
    line1Loc = (25, 50)
    line2 = str(unitCount) + ' ' + unitType
    line2Loc = (25, 75)
    line3 = 'Press ENTER when done.'
    line3Loc = (25, 100)

    cv2.putText(img, line1, line1Loc, font, 1, (255, 255, 255), 1)
    cv2.putText(img, line2, line2Loc, font, 1, (255, 255, 255), 1)
    cv2.putText(img, line3, line3Loc, font, 1, (255, 255, 255), 1)



    
## Helper Functions: Section 2 -- Mathematical Utility Functions

# 2nd-order central difference method for calculating the derivative of unevenly spaced data
def calcDeriv(f, t):
    df = np.empty(len(f))
    df[0] = (f[1] - f[0]) / (t[1] - t[0])
    df[len(f)-1] = (f[len(f)-1] - f[len(f)-2]) / (t[len(f)-1] - t[len(f)-2])
    df[1:len(f)-1] = f[0:len(f)-2]*((t[1:len(f)-1] - t[2:len(f)]) / ((t[0:len(f)-2] - t[1:len(f)-1])*(t[0:len(f)-2] - t[2:len(f)]))) + f[1:len(f)-1]*(((2*t[1:len(f)-1]) - t[0:len(f)-2] - t[2:len(f)]) / ((t[1:len(f)-1] - t[0:len(f)-2])*(t[1:len(f)-1] - t[2:len(f)]))) + f[2:len(f)]*((t[1:len(f)-1] - t[0:len(f)-2]) / ((t[2:len(f)] - t[0:len(f)-2])*(t[2:len(f)] - t[1:len(f)-1]))) 
    return df

# Calculates a polynomial fit of degree "deg" though an array of data "y" with corresponding x values "x"
def splineFit(x, y, deg):
    fit = np.polyfit(x, y, deg)
    yfit = np.zeros(len(y))
    for i in range(deg+1):
        yfit += fit[i]*(x**(deg-i))
    return yfit


# The following functions assist in estimating the coefficient of friction of the user's table by fitting their data
# to a damped harmonic oscillator. This functionality is not implemented in the current release of DigiPyRo
def errFuncPolar(params, data):
    modelR = np.abs(params[0]*np.exp(-data[0]*params[3]*params[1])*np.cos((params[3]*data[0]*((1-(params[1]**2))**(0.5))) - params[2]))
    modelTheta = createModelTheta(data[0], params, data[2][0])
    model = np.append(modelR, modelR*modelTheta)
    datas = np.append(data[1], data[1]*data[2])
    return model - datas

def fitDataPolar(data, guess):
    result = sp.optimize.leastsq(errFuncPolar, guess, args=(data), full_output=1)
    return result[0]

def createModelR(bestfit, t):
    return np.abs(bestfit[0]*np.exp(-t*bestfit[3]*bestfit[1])*np.cos((bestfit[3]*t*((1-(bestfit[1]**2))**(0.5)) - bestfit[2])))

def createModelTheta(t, bestfit, thetai):
    wd = bestfit[3] * ((1 - (bestfit[1])**2)**(0.5))
    period = (2*np.pi)/wd
    phi = bestfit[2]
    theta = np.ones(len(t))*thetai
    for i in range(len(t)):
        phase = (wd*t[i])-phi
        while phase > 2*np.pi:
            phase -= 2*np.pi
        while phase < 0:
            phase += 2*np.pi

        if phase < (np.pi/2) or phase > ((3*np.pi)/2):
           theta[i] = thetai
        elif phase > (np.pi/2) and phase < ((3*np.pi)/2):
           theta[i] = thetai + np.pi
        theta[i] += t[i]*(-bestfit[4])
        
        while theta[i] > 2*np.pi:
           theta[i] -= 2*np.pi
        while theta[i] < 0:
           theta[i] += 2*np.pi
     
    return theta

#####################
### Main function ###
#####################
# This function is executed when the user presses the "Start!" button on the GUI

def start():
    filename = filenameVar.get()     # get full path to input video
    vid = cv2.VideoCapture(filename) # input video

    global width, height, numFrames, fps, fourcc, video_writer, spinlab, npts # declare these variables as global so they can be used by helper functions without being explicitly passed as arguments
    npts = 0 # number of user-clicked points along circumference of circle/polygon
    spinlab = cv2.imread('SpinLabUCLA_BW_strokes.png') # spinlab logo to display in upper right corner of output video
    width = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH)) 
    height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT)) # read the width and height of input video. output video will have matching dimensions
    fps = fpsVar.get()
    fileName = savefileVar.get()
    fourcc = cv2.VideoWriter_fourcc('m','p','4','v') # codec for output video
    video_writer = cv2.VideoWriter(fileName+'.avi', fourcc, fps, (width, height)) # VideoWriter object for editing and saving the output video

    spinlab = cv2.resize(spinlab,(int(0.2*width),int((0.2*height)/3)), interpolation = cv2.INTER_CUBIC) # resize spinlab logo based on input video dimensions

    global naturalRPM, physicalRPM, digiRPM, camRPM, dtheta, per, custMask, changeUnits, unitType, unitCount, unitConv # declare these variables as global so they can be used by helper functions without being explicitly passed as arguments
    naturalRPM = tableRPMVar.get()
    naturalOmega = (naturalRPM * 2*np.pi)/60
    camRPM = camRPMVar.get()
    digiRPM = digiRPMVar.get()
    totRPM = camRPM + digiRPM
    totOmega = (totRPM *2*np.pi)/60
    dtheta = digiRPM*(6/fps)
    addRot = digiRPM != 0

    changeUnits = unitVar.get()
    unitType = unitTypeVar.get()
    unitCount = unitCountVar.get()
    unitConv = 1 			# intialize to 1 in the case that no unit conversion is selected

    startFrame = fps*startTimeVar.get()
    if startFrame == 0:
        startFrame = 1
    numFrames = int(fps*(endTimeVar.get() - startTimeVar.get()))
    custMask = customMaskVar.get()
    trackBall = trackVar.get()
    makePlots = plotVar.get()

    # Close GUI window so rest of program can run
    root.destroy()

    global center, frame, xpoints, ypoints, r, poly1, poly2 # declare these variables as global so they can be used by helper functions without being explicitly passed as arguments

    # Open first frame from video, user will click on center
    vid.set(cv2.CAP_PROP_POS_FRAMES, startFrame) # set the first frame to correspond to the user-selected start time
    ret, frame = vid.read() # read the first frame from the input video
    frame = cv2.resize(frame,(width,height), interpolation = cv2.INTER_CUBIC) # ensure frame is correct dimensions
    cv2.namedWindow('CenterClick')

    # Use the appropriate mask-selecting function (depending on whether custom-shaped mask is checked)
    if custMask:
        cv2.setMouseCallback('CenterClick', nGon)
    else:
        cv2.setMouseCallback('CenterClick', circumferencePoints)

    # Append instructions to screen
    instructsCenter(frame)
    orig = frame.copy()
    while(1):
        cv2.imshow('CenterClick', frame)
        k = cv2.waitKey(0)
        if k == 13: # user presses ENTER
            break
        elif k == 127: # user presses BACKSPACE/DELETE
            removePoint(orig)

    cv2.destroyWindow('CenterClick')

    # Select initial position of ball (only if particle tracking is selected)
    if trackBall:
        vid.set(cv2.CAP_PROP_POS_FRAMES, startFrame)
        ret, frame = vid.read()
        frame = cv2.resize(frame,(width,height), interpolation = cv2.INTER_CUBIC)
        cv2.namedWindow('Locate Ball')
        cv2.setMouseCallback('Locate Ball', locate)

        instructsBall(frame)
        cv2.imshow('Locate Ball', frame)
        cv2.waitKey(0)
        cv2.destroyWindow('Locate Ball')

    # Draw a line to calculate a pixel-to-distance conversion factor
    if changeUnits:
        vid.set(cv2.CAP_PROP_POS_FRAMES, startFrame)
        ret, frame = vid.read()
        frame = cv2.resize(frame,(width,height), interpolation = cv2.INTER_CUBIC)
        cv2.namedWindow('Distance Calibration')
        cv2.setMouseCallback('Distance Calibration', unitConversion)
        
        instructsUnit(frame)
        cv2.imshow('Distance Calibration', frame)
        cv2.waitKey(0)
        cv2.destroyWindow('Distance Calibration')

    vid.set(cv2.CAP_PROP_POS_FRAMES, startFrame) # reset video to first frame

    # allocate empty arrays for particle-tracking data
    t = np.empty(numFrames)
    ballX = np.empty(numFrames)
    ballY = np.empty(numFrames)
    if trackBall:
        ballPts = 0 #will identify the number of times that Hough Circle transform identifies the ball
        lastLoc = particleCenter # most recent location of particle, initialized to the location the user selected
        thresh = 50
        trackingData = np.zeros(numFrames) # logical vector which tells us if the ball was tracked at each frame
    framesArray = np.empty((numFrames,height,width,3), np.uint8)
    
    # Go through the input movie frame by frame and do the following: (1) digitally rotate, (2) apply mask, (3) center the image about the point of rotation, (4) search for particle and record tracking results
    for i in range(numFrames):
        # Read + resize current frame
        ret, frame = vid.read() # read next frame from video
        frame = cv2.resize(frame,(width,height), interpolation = cv2.INTER_CUBIC)

        # (1) and (2) (the order they are applied depends on whether the movie is derotated)
        if totRPM != 0: # Case 1: the mask is applied before rotation so it co-rotates with the additional digital rotation
            cv2.fillPoly(frame, np.array([poly1, poly2]), 0) # black out everything outside the region of interest
            cv2.circle(frame, center, 4, (255,0,0), -1) # place a circle at the center of rotation
        
        if addRot:
            M = cv2.getRotationMatrix2D(center, i*dtheta, 1.0)
            frame = cv2.warpAffine(frame, M, (width, height))
            if totRPM == 0: # Case 2: the movie is de-rotated, we want to apply the mask after digital rotation so it is stationary
                cv2.fillPoly(frame, np.array([poly1, poly2]), 0)
        else:
            cv2.fillPoly(frame, np.array([poly1, poly2]), 0)
        
        # (3)
        frame = centerImg(frame, center[0], center[1]) # center the image
    
    
        centered = cv2.resize(frame,(width,height), interpolation = cv2.INTER_CUBIC) # ensure the frame is the correct dimensions
        
        # (4)
        if trackBall: # if tracking is turned on, apply tracking algorithm
            gray = cv2.cvtColor(centered, cv2.COLOR_BGR2GRAY) # convert to black and whitee
            gray = cv2.medianBlur(gray,5) # blur image. this allows for better identification of circles
            ballLoc = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 20, param1=50, param2=10, minRadius = int(particleRadius * 0.6), maxRadius = int(particleRadius * 1.4))
            if type(ballLoc) != NoneType : # if a circle is identified, record it
                for j in ballLoc[0,:]:
                    if (np.abs(j[0] - lastLoc[0]) < thresh) and (np.abs(j[1] - lastLoc[1]) < thresh):    
                        cv2.circle(centered, (j[0],j[1]), j[2], (0,255,0),1)
                        cv2.circle(centered, (j[0],j[1]), 2, (0,0,255), -1)
                        ballX[ballPts] = j[0]
                        ballY[ballPts] = j[1]
	                t[ballPts] = i/fps
                        lastLoc = np.array([j[0],j[1]])      
                        ballPts += 1
                        trackingData[i] = 1
                        break
            
            # mark the frame with dots to indicate the particle path
            for k in range(ballPts-1):
                cv2.circle(centered, (int(ballX[k]), int(ballY[k])), 1, (255,0,0), -1)    	


        annotateImg(centered, i) # apply diagnostic information and logos to each frame
        framesArray[i] = centered # save each frame in an array so that we can loop back through later and add the inertial radius

    # Done looping through video

    # Reformat tracking data
    if trackBall:
        ballX = ballX[0:ballPts] # shorten the array to only the part which contains tracking info
        ballY = ballY[0:ballPts]
        t = t[0:ballPts]
        ballX -= center[0] # set the center of rotation as the origin
        ballY -= center[1] # "                                      "
        
        # Convert from pixels to units of distance
        ballX *= unitConv
        ballY *= unitConv
    
        ballR = ((ballX**2)+(ballY**2))**(0.5) # convert to polar coordinates
        ballTheta = np.arctan2(ballY, ballX)   # "                          "
        for i in range(len(ballTheta)):        # ensure that the azimuthal coordinate is in the range [0, 2*pi]
            if ballTheta[i] < 0:
                ballTheta[i] += 2*np.pi

        # Calculate velocities
        ux = calcDeriv(ballX, t)
        uy = calcDeriv(ballY, t)
        ur = calcDeriv(ballR, t)
        utheta = calcDeriv(ballTheta, t)
        utot = ((ux**2)+(uy**2))**(0.5)

        fTh = 2*totOmega                           # theoretical inertial frequency
        rInert = utot / fTh                        # inertial radius, a combination of theory (fTh) and data (utot)
        rInertSmooth = splineFit(t, rInert, 20)    # polynomial fit of degree 20 (provides a smooth fit through the data and solves the uneven sampling problem)
        uxSmooth = splineFit(t, ux, 20)
        uySmooth = splineFit(t, uy, 20)


        # If option to make plots of tracking data is selected, make plots
        if makePlots:
            plt.figure(1)
            plt.subplot(211)
            plt.plot(t, ballR, 'r1')
            plt.xlabel(r"$t$ (s)")
            plt.ylabel(r"$r$")

            plt.subplot(212)
            plt.plot(t, ballTheta, 'r1')
            plt.xlabel(r"$t$ (s)")
            plt.ylabel(r"$\theta$")
            plt.savefig(fileName+'_polar.pdf', format = 'pdf', dpi = 1200)

            plt.figure(2)
            plt.subplot(211)
            plt.plot(t, ballX, 'r1')
            plt.xlabel(r"$t$ (s)")
            plt.ylabel(r"$x$")
            plt.subplot(212)
            plt.plot(t, ballY, 'b1')
            plt.xlabel(r"$t$ (s)")
            plt.ylabel(r"$y$")
            plt.savefig(fileName+'_cartesian.pdf', format = 'pdf', dpi =1200)   

            plt.figure(3)
            plt.subplot(221)
            plt.plot(t, ux, label=r"$u_x$")
            plt.plot(t, uy, label=r"$u_y$")
            plt.xlabel(r"$t$ (s)")
            plt.legend(loc = 'upper right', fontsize = 'x-small')
            plt.subplot(222)
            plt.plot(t, rInert)
            plt.plot(t, rInertSmooth)
            plt.xlabel(r"$t$ (s)")
            plt.ylabel(r"$r_i$")
            plt.subplot(223)
            plt.plot(t, ur)
            plt.xlabel(r"$t$ (s)")
            plt.ylabel(r"$u_r$")
            plt.subplot(224)
            plt.plot(t, utheta)
            plt.xlabel(r"$t$ (s)")
            plt.ylabel(r"$u_{\theta}$")
            plt.ylim([-3*np.abs(totOmega), 3*np.abs(totOmega)])
            plt.tight_layout(pad = 1, h_pad = 0.5, w_pad = 0.5)
            plt.savefig(fileName+'_derivs.pdf', format = 'pdf', dpi =1200)


        # Record tracking data in a .txt file
        dataList = np.array([t, ballX, ballY, ballR, ballTheta, ux, uy, ur, utheta, utot])

        dataFile = open(fileName+'_data.txt', 'w')
        dataFile.write('DigiPyRo Run Details \n \n')
        dataFile.write('Original File: ' + filename + '\n' + 'Output File: ' + fileName + '\n')
        dataFile.write('Date of run: ' + time.strftime("%c") + '\n \n')
        dataFile.write('Original rotation of camera: ' + str(camRPM) + ' RPM\n' + 'Added digital rotation: ' + str(digiRPM) + ' RPM\n' + 'Curvature of surface: ' + str(naturalRPM) + ' RPM\n' + '\n' + 'Particle Tracking Data')
        dataFile.write(' in ' + unitType + ' and ' + unitType + '/s\n') 
        dataFile.write('t x y r theta u_x u_y u_r u_theta ||u||\n')
        
        for i in range(len(ballX)):
            for j in range(len(dataList)):
                entry = "%.2f" % dataList[j][i]
                if j < len(dataList) - 1:
                    dataFile.write(entry + ' ')
                else:
                    dataFile.write(entry + '\n')
        dataFile.close()

    cv2.destroyAllWindows()	# close any open windows
    vid.release()		# release the video

    # Loop through video and report inertial radius 
    numRadii = 25 			# number of inertial radii which will be shown at one time on the screen
    rInertSmooth[0:3] = 0
    rInertSmooth[ballPts-3:ballPts] = 0 # the first and last few inertial radii tend to have very large systematic errors. Set them to 0 so that they are not shown
    if trackBall and totRPM != 0:	# only do this if particle tracking is selected and the inertial radius is not infinite (happens when totRPM = 0)
        index=0
        lineStartX = np.empty(ballPts, dtype=np.int16)
        lineStartY = np.empty(ballPts, dtype=np.int16)
        lineEndX = np.empty(ballPts, dtype=np.int16)
        lineEndY = np.empty(ballPts, dtype=np.int16)
        for i in range(numFrames):
            frame = framesArray[i]
            if trackingData[i]:
                (lineStartX[index], lineStartY[index]) = (int(0.5+ballX[index]+center[0]), int(0.5+ballY[index]+center[1]))
                angle = np.arctan2(uySmooth[index],uxSmooth[index])
                rad = rInertSmooth[index]
                (lineEndX[index], lineEndY[index]) = (int(0.5+center[0]+ballX[index]+(rad*np.sin(angle))), int(0.5+center[1]+ballY[index]-(rad*np.cos(angle))))
                if index < numRadii:
                    numLines = index
                else:
                    numLines = numRadii
                for j in range(numLines):
                    cv2.line(frame, (lineStartX[index-j], lineStartY[index-j]), (lineEndX[index-j], lineEndY[index-j]), (int(255), int(255), int(255)), 1)
                index+=1
            video_writer.write(frame)
    else:
        for i in range(numFrames):
            frame = framesArray[i]
            video_writer.write(frame)
    
    video_writer.release()

#######################
### Create GUI menu ###
#######################

root = Tk()
root.title('DigiPyRo')
startButton = Button(root, text = "Start!", command = start)
startButton.grid(row=11, column=0)

tableRPMVar = DoubleVar()
tableRPMEntry = Entry(root, textvariable=tableRPMVar)
tableLabel = Label(root, text="Curvature of table (in RPM, enter 0 for a flat surface):")
tableRPMEntry.grid(row=0, column=1)
tableLabel.grid(row=0, column=0)

digiRPMVar = DoubleVar()
camRPMVar  = DoubleVar()
digiRPMEntry = Entry(root, textvariable=digiRPMVar)
camRPMEntry  = Entry(root, textvariable=camRPMVar)
digiLabel = Label(root, text="Additional digital rotation (RPM):")
camLabel  = Label(root, text="Physical rotation (of camera, RPM):")
digiRPMEntry.grid(row=2, column=1)
camRPMEntry.grid(row=1, column=1)
digiLabel.grid(row=2, column=0)
camLabel.grid(row=1, column=0)

customMaskVar = BooleanVar()
customMaskEntry = Checkbutton(root, text="Custom-Shaped Mask (checking this box allows for a polygon-shaped mask. default is circular)", variable=customMaskVar)
customMaskEntry.grid(row=3, column=0)

filenameVar = StringVar()
filenameEntry = Entry(root, textvariable = filenameVar)
filenameLabel = Label(root, text="Full filepath to movie:")
filenameEntry.grid(row=4, column=1)
filenameLabel.grid(row=4, column=0)

savefileVar = StringVar()
savefileEntry = Entry(root, textvariable = savefileVar)
savefileLabel = Label(root, text="Save output video as:")
savefileEntry.grid(row=5, column=1)
savefileLabel.grid(row=5, column=0)

startTimeVar = DoubleVar()
endTimeVar = DoubleVar()
startTimeEntry = Entry(root, textvariable = startTimeVar)
endTimeEntry = Entry(root, textvariable = endTimeVar)
startTimeLabel = Label(root, text="Start and end times (in seconds):")
startTimeLabel.grid(row=6, column=0)
startTimeEntry.grid(row=6, column=1)
endTimeEntry.grid(row=6, column=2)

trackVar = BooleanVar()
trackEntry = Checkbutton(root, text="Track Ball", variable=trackVar)
trackEntry.grid(row=5, column=2)
plotVar = BooleanVar()
plotEntry = Checkbutton(root, text="Create plots with tracking results", variable=plotVar)
plotEntry.grid(row=5, column=3)

fpsVar = DoubleVar()
fpsEntry = Entry(root, textvariable=fpsVar)
fpsLabel = Label(root, text="Frames per second of video:")
fpsEntry.grid(row=7, column=1)
fpsLabel.grid(row=7, column=0)

unitVar = BooleanVar()
unitEntry = Checkbutton(root, text="Add distance units calibration", variable=unitVar)
unitEntry.grid(row=8,column=0)
unitTypeVar = StringVar()
unitTypeEntry = Entry(root, textvariable = unitTypeVar)
unitTypeLabel = Label(root, text="Length unit (e.g. cm, ft):")
unitCountVar = DoubleVar()
unitCountLabel = Label(root, text="Unit count:")
unitCountEntry = Entry(root, textvariable = unitCountVar)
unitTypeLabel.grid(row=8, column=1)
unitTypeEntry.grid(row=8, column=2)
unitCountLabel.grid(row=8, column=3)
unitCountEntry.grid(row=8, column=4)

root.mainloop()
