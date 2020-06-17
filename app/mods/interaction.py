import cv2
import numpy as np


def selection_window(video, dim, start):
    global npts, center, frame, xpoints, ypoints, r, poly1, poly2

    npts = 0
    video.set(cv2.CAP_PROP_POS_FRAMES, start)
    ret, frame = video.read()
    frame = cv2.resize(frame, dim, interpolation=cv2.INTER_CUBIC)

    cv2.namedWindow('Select Circle')
    cv2.setMouseCallback('Select Circle', select_circle)

    instructions_circle(frame)
    orig = frame.copy()

    while 1:
        cv2.imshow('Select Circle', frame)
        k = cv2.waitKey(0)
        if k == 13:
            break
        elif k == 127:
            remove_point(orig)

    cv2.destroyWindow('Select Circle')
    return poly1, poly2, center


# User clicks points along the circumference of a circular ROI. This function
# records the points and calculates the best-fit circle through the points.
def select_circle(event, x, y, flags, param):
    global npts, center, frame, xpoints, ypoints, r, poly1, poly2
    # if user clicks
    if event == cv2.EVENT_LBUTTONDOWN:
        # if this is the first point, intialize the arrays of x-y coords
        if (npts == 0):
            xpoints = np.array([x])
            ypoints = np.array([y])
        # otherwise, append the points to the arrays
        else:
            xpoints = np.append(xpoints,x)
            ypoints = np.append(ypoints,y)
        npts+=1
        cv2.circle(frame, (x,y), 3, (0,255,0), -1)
        clone = frame.copy()
        # if there are more than 2 points, calculate the best-fit circle
        # through the points
        if (len(xpoints) > 2):
            bestfit = calc_center(xpoints, ypoints)
            center = (bestfit[0], bestfit[1])
            r = bestfit[2]

            poly1 = np.array([[0,0],
                              [frame.shape[1],0],
                              [frame.shape[1],frame.shape[0]],
                              [0,frame.shape[0]]])

            poly2 = np.array([[bestfit[0]+r,
                               bestfit[1]]])
            circpts = 100
            # approximate the circle as a 100-gon
            # which makes it easier to draw the mask,
            # as we define the mask region as the area between two polygons
            for i in range(1,circpts):
                theta =  2 * np.pi * (i / circpts)
                nextpt = np.array([[int(bestfit[0] + (r * np.cos(theta))),
                                    int(bestfit[1] + (r * np.sin(theta)))]])
                poly2 = np.append(poly2, nextpt, axis=0)

            cv2.circle(frame, center, 4, (255,0,0), -1)
            cv2.circle(frame, center, r, (0,255,0), 1)

        cv2.imshow('Select Circle', frame)
        frame = clone.copy()

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

# def calc_center(xp, yp):
    # # arguments used in computations
    # xp2 = xp**2
    # yp2 = yp**2
    # xy = xp * yp
#
    # circleArr = np.array([[np.sum(xp2), np.sum(xy), np.sum(xp)],
                          # [np.sum(xy), np.sum(yp2), np.sum(yp)],
                          # [np.sum(xp), np.sum(yp), len(xp)]])
#
    # circleVec = np.array([np.sum(xp * (xp2 + yp2)),
                          # np.sum(yp * (xp2 + yp2)),
                          # np.sum(xp2 + yp2)])
#
    # circleInv = np.linalg.inv(circleArr)
#
    # # matric multiplication
    # M = (circleInv @ circleVec).T
#
    # xc = M[0] / 2
    # yc = M[1] / 2
    # d = M[0]**2 + M[1]**2 + M[2] * 4
    # diam = np.sqrt(d)
    # return np.array([int(xc), int(yc), int(diam / 2)])


# Displays instructions on the screen for identifying the
# circle of interest
def instructions_circle(img):
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


def remove_point(orig):
    global npts, center, frame, xpoints, ypoints, r, poly1, poly2
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

    # if there are more than 2 points after removing the most recent point,
    # recalculate the center of rotation and the mask region
    if (len(xpoints) > 2):
        bestfit = calc_center(xpoints, ypoints)
        center = (bestfit[0], bestfit[1])
        r = bestfit[2]
        poly1 = np.array([[0,0], [frame.shape[1],0],
                         [frame.shape[1],frame.shape[0]],
                         [0,frame.shape[0]]])

        poly2 = np.array([[bestfit[0]+r, bestfit[1]]])
        circpts = 100
        for i in range(1,circpts):
            theta =  2 * np.pi * (float(i) / circpts)

            nextpt = np.array([[int(bestfit[0] + (r * np.cos(theta))),
                                int(bestfit[1] + (r * np.sin(theta)))]])

            poly2 = np.append(poly2,nextpt,axis=0)

        cv2.circle(frame, center, 4, (255,0,0), -1)
        cv2.circle(frame, center, r, (0,255,0), 1)
        cv2.imshow('Select Circle', frame)


# Shifts image so that it is centered at (x_c, y_c)
def center_frame(img, x_c, y_c, dim):
    width = dim[0]
    height = dim[1]

    dx = (width / 2) - x_c
    dy = (height / 2) - y_c
    shiftMatrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, shiftMatrix, (width, height))
