#!/usr/bin/env python
import rospy, tf, math, numpy
import heapq
import copy
from geometry_msgs.msg import Twist
from nav_msgs.msg import GridCells
from nav_msgs.msg import Odometry, OccupancyGrid
from geometry_msgs.msg import PoseStamped, Pose, Point, PoseWithCovarianceStamped
from kobuki_msgs.msg import BumperEvent
from std_msgs.msg import String
from tf.transformations import euler_from_quaternion
from heapdict import heapdict

wheel_base = 0.2286 #m
wheel_diam = 0.07 #m

global eightconnected
global fourconnected

eightconnected = True
fourconnected = False

robot_size = 0.25

class PQueue:
    def __init__(self):
        self._queue = []
        self._index = 0

        def push(self, item, priority):
            heapq.heappush(self._queue, (priority, self._index, item))
            self._index +=1

        def pop(self):
            return heapq.heappop(self._queue)[-1]

class aNode:
    def __init__(self, index, val, hestimate, gcost, adjacent):
        self.index = index
        self.point = getWorldPointFromIndex(index)
        self.val = val
        self.weight = val
        self.hestimate = hestimate
        self.gcost = gcost
        self.adjacent = list()
        self.f = 0
        self.cameFrom = -1

    def appendAdjacent(self, index):
        self.adjacent.append(index)

    def setupParent(self, index):
        self.cameFrom = (index)

def noFilter(path): #takes the parsed path & tries to remove unecessary zigzags 
    returnPath = list()
    for i,node in enumerate(path):
        point = Point()
        currNode = path[i]
        point.x = getWorldPointFromIndex(currNode).x
        point.y = getWorldPointFromIndex(currNode).y
        point.z = 0
        
        returnPath.append(point)
        #print "Point in Path: X: %f Y: %f" % (point.x, point.y)
    return returnPath

def mapCallBack(data):
    global mapData
    global width
    global height
    global mapgrid
    global resolution
    global offsetX
    global offsetY

    mapgrid = data
    resolution =data.info.resolution
    mapData = data.data
    width = data.info.width
    height = data.info.height
    offsetX = data.info.origin.position.x
    offsetY = data.info.origin.position.y

    print data.info

def getStart(_startPos):
    global startRead
    startRead = True
    global startPosX
    global startPosY
    global startPos
    global startIndex
    global odom_list

    startPos = _startPos
    startPosX = pose.position.x #startPos.pose.pose.position.x
    startPosY = pose.position.y #startPos.pose.pose.position.y

    startIndex = getIndexFromWorldPoint(startPosX, startPosY)

    point = getWorldPointFromIndex(startIndex)
    
    
    print "Printing start pose"
    print startPos.pose.pose
    print "Calculated world position: %f, %f Index: %i" % (point.x, point.y, startIndex)

def readGoal(goal):
    global goalRead
    goalRead = True
    global goalX
    global goalY
    global goalIndex
    global goalPhi
    global goalOrientation

    goalX= goal.pose.position.x
    goalY= goal.pose.position.y
    
    goalIndex = getIndexFromWorldPoint(goalX,goalY)
    print "Printing goal pose"
    print goal.pose

    goalOrientation = goal.pose.orientation
    quaternion = (pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w)
    roll, pitch, yaw = euler_from_quaternion(quaternion)

    pose.orientation.z = yaw
    goalPhi = math.degrees(yaw)
# returns the index number given a point in the world
def getIndexFromPoint(x,y):
    global Point

    return int(((y)*width) + x)

#returns in meters the point of the current index
def getWorldPointFromIndex(index):
    
    global Point
    global offsetX
    global offsetY

    point=Point()
    #print "GetX: %i" % getX(index)
    point.x=(getX(index)*resolution)+offsetX + (1.5 * resolution)
    point.y=(getY(index)*resolution)+offsetY + (.5 * resolution)
    point.z=0
    return point

# returns the index number given a point in the world
def getIndexFromWorldPoint(x,y):
    #calculate the index coordinates
    indexX = int(((x-offsetX) - (1.5*resolution))/resolution)
    indexY = int(((y-offsetY) - (.5*resolution))/resolution)
    
    index = int (((indexY)*width) + indexX) 
    
    print index 
    return index

def heuristic(index): 
    current = getWorldPointFromIndex(index)
    h = math.sqrt(pow(goalX-current.x,2)+pow(goalY-current.y,2))
    return h

def finalCheck(cIndex, fIndex): 
    cPoint = getWorldPointFromIndex(cIndex)
    fPoint = getWorldPointFromIndex(fIndex)
    
    if(abs(cPoint.x - fPoint.x) < 3*resolution): 
        if(abs(cPoint.y - fPoint.y) < 3*resolution):
            return True
    else: 
        return False

#returns the x value of the index
def getX(index):
    adjusted = index + 1
    if (adjusted % width) == 0:
        return width - 1
    else:
        return (adjusted % width) - 1

#returns the y value of the index
def getY(index):
    adjusted = index
    return math.floor(adjusted/width)
    
#checks if the passed point is in the map
def isInMap(point):
    #catch if point is negative
    if(point.x < 0 or point.y < 0):
        return False
    # is point within 0 and width and 0 and height?
    if( ( 0 <= point.x and width > point.x) and ( 0 <= point.y and height > point.y)):
        return True
    else:
        return False

#returns index of point above this one, only works for non-first row
def pointNorth(point):
    output = copy.deepcopy(point)
    output.y += 1
    return output

#returns index of point below this one, only works for non-last row
def pointSouth(point):
    output = copy.deepcopy(point)
    output.y -= 1
    return output

#returns index of point right of this one, only works for non-last column
def pointEast(point):
    output = copy.deepcopy(point)
    output.x += 1
    return output

#returns index of point right of this one, only works for non-first column
def pointWest(point):
    output = copy.deepcopy(point)
    output.x -= 1
    return output

def pointNorthwest(point): 
    return pointWest(pointNorth(point))

def pointNortheast(point): 
    return pointEast(pointNorth(point))

def pointSouthwest(point):
    return pointWest(pointSouth(point))

def pointSoutheast(point): 
    return pointEast(pointSouth(point)) 

def linkMap():   
    for i in range(0, height*width):
        currentPoint = Point()
        currentPoint.x = getX(i)
        currentPoint.y = getY(i)
        #print "I is %i, x is %i, y is %i" % (i, currentPoint.x, currentPoint.y)
        # try adding north
        if(isInMap(pointAbove(currentPoint))):  
            myPoint = pointAbove(currentPoint)
            #print "My Point X: %i Y: %i calc Index: %i" % (myPoint.x, myPoint.y,getIndexFromPoint(myPoint.x,myPoint.y))
            G[i].appendAdjacent(getIndexFromPoint(myPoint.x,myPoint.y))
        currentPoint.x = getX(i)
        currentPoint.y = getY(i)
        # try adding east
        if(isInMap(pointRight(currentPoint))):
            myPoint = pointRight(currentPoint)
            #print "My Point X: %i Y: %i calc Index: %i" % (myPoint.x, myPoint.y,getIndexFromPoint(myPoint.x,myPoint.y))
            G[i].appendAdjacent(getIndexFromPoint(myPoint.x,myPoint.y))
        currentPoint.x = getX(i)
        currentPoint.y = getY(i)
        # try adding south
        if(isInMap(pointBelow(currentPoint))):
            myPoint = pointBelow(currentPoint)
            #print "My Point X: %i Y: %i calc Index: %i" % (myPoint.x, myPoint.y,getIndexFromPoint(myPoint.x,myPoint.y))
            G[i].appendAdjacent(getIndexFromPoint(myPoint.x,myPoint.y))
        currentPoint.x = getX(i)
        currentPoint.y = getY(i)
        # try adding west
        if(isInMap(pointLeft(currentPoint))):
            myPoint = pointLeft(currentPoint)
            #print "My Point X: %i Y: %i  calc Index: %i" % (myPoint.x, myPoint.y,getIndexFromPoint(myPoint.x,myPoint.y))
            G[i].appendAdjacent(getIndexFromPoint(myPoint.x,myPoint.y))

def connectNeighbors(index, eightconnected):
    adjList = list() 

    currentPoint = Point()
    currentPoint.x = getX(index)
    currentPoint.y = getY(index)
    
    if eightconnected:
        #print "I is %i, x is %i, y is %i" % (i, currentPoint.x, currentPoint.y)
        # try adding north
        if(isInMap(pointNorth(currentPoint))):  
            myPoint = pointNorth(currentPoint)
            adjList.append(getIndexFromPoint(myPoint.x,myPoint.y))
        currentPoint.x = getX(index)
        currentPoint.y = getY(index)
        # try adding east
        if(isInMap(pointEast(currentPoint))):
            myPoint = pointEast(currentPoint)
            adjList.append(getIndexFromPoint(myPoint.x,myPoint.y))
        currentPoint.x = getX(index)
        currentPoint.y = getY(index)
        # try adding south
        if(isInMap(pointSouth(currentPoint))):
            myPoint = pointSouth(currentPoint)
            adjList.append(getIndexFromPoint(myPoint.x,myPoint.y))
        currentPoint.x = getX(index)
        currentPoint.y = getY(index)
        # try adding west
        if(isInMap(pointWest(currentPoint))):
            myPoint = pointWest(currentPoint)
            adjList.append(getIndexFromPoint(myPoint.x,myPoint.y))
#----------------- Diagonals -------------------------------# 

    if(isInMap(pointNorthwest(currentPoint))): 
        myPoint = pointNorthwest(currentPoint)
        adjList.append(getIndexFromPoint(myPoint.x,myPoint.y))

    currentPoint.x = getX(index)
    currentPoint.y = getY(index)
    # try adding east
    if(isInMap(pointNortheast(currentPoint))):
        myPoint = pointNortheast(currentPoint)     
        adjList.append(getIndexFromPoint(myPoint.x,myPoint.y))

    currentPoint.x = getX(index)
    currentPoint.y = getY(index)
    # try adding south
    if(isInMap(pointSouthwest(currentPoint))):
        myPoint = pointSouthwest(currentPoint)     
        adjList.append(getIndexFromPoint(myPoint.x,myPoint.y))

    currentPoint.x = getX(index)
    currentPoint.y = getY(index)
    # try adding west
    if(isInMap(pointSoutheast(currentPoint))):
        myPoint = pointSoutheast(currentPoint)
        adjList.append(getIndexFromPoint(myPoint.x,myPoint.y))


    return adjList

def initMap(_mapGrid):

    initObs()
    newMap = list()
    global G

    G = list()

    print "creating map"
    global frontier
    frontier = list()

    for i in range(0, width*height):
        node = aNode(i,mapData[i],heuristic(i),0,0.0)
        G.append(node) 
        frontier.append(0)
    
    #TODO Fix expand obs 
    expandedMap = list()
    expandedMap = padObstacles(newMap)

    padObstacles(G)
    
    print "map created" 
    return expandedMap


def calcG(currentG, neighborG):
    if (neighborG == 0): 
        neighborG = currentG + resolution
    return neighborG

def adjCellCheck(current):
    global adjList
    global traversal

    #adjList =  current.adjacent ## list of indexes of neighbor 
    adjList = connectNeighbors(current.index, True)
    for index in adjList:
        currCell = G[index] 

        if(currCell.weight != -1) and (currCell.weight <= 93): 
            evalNeighbor(currCell, current) 
            traversal.append(G[index])
    
    publishTraversal(traversal)

def evalNeighbor(nNode, current): #check to see if in the closed set
    if(nNode not in closedSet): 
        tentative = current.gcost + resolution 
        if (nNode not in openSet) or (tentative < nNode.gcost): 
            if (nNode not in openSet):
                openSet.append(nNode)
            nNode.gcost = calcG(current.gcost+nNode.gcost, nNode.gcost)
            nNode.f = nNode.gcost + 2*nNode.hestimate
            G[nNode.index].cameFrom = current.index
    else:
        lowestInQ(openSet)

def lowestInQ(nodeSet): 
    costList = list() 
    for node in nodeSet:
        costList.append(node.f)

    a = costList.index(min(costList))
    mapIndex = nodeSet[a].index
    return mapIndex

def reconPath(current, start): 
    total_path = list()
    total_path.append(current.index)
            
    while (current.cameFrom != -1):
        current = G[current.cameFrom]
        total_path.append(current.cameFrom)     
             
    return total_path


def aStar():
    
    global G
    G = list()
    initMap(mapgrid)  # add all nodes to grah, link all nodes

    global path 
    path = list()
    global openSet
    global closedSet
    global eightconnected

    global traversal
    traversal = list()
    global frontier
    frontier = list()

    openSet = list()
    openSet.append(G[startIndex])        #Add first node to openSet # set priority to distance
    closedSet = list()         #everything that has been examined
    
    print "start a*"
    
    print len(openSet)
    #print openSet[0].index

    while openSet:  

        try:

            i = lowestInQ(openSet) 
            current = G[i]
            if current in frontier: 
                frontier.remove(current)
            #print G[i].cameFrom
            if (current.index == goalIndex): 
                print reconPath(current, G[startIndex])
                                
                return reconPath(current, startIndex)
                pass
            openSet.remove(current)
            closedSet.append(current)       
            adjCellList = adjCellCheck(current)
            if adjCellList:
                for node in adjCellList:
                    if node not in closedSet:
                        frontier.append(node)
                        publishFrontier(frontier)
        except KeyboardInterrupt: 
            break
    
    print "No route to goal"

def getWaypoints(path): #calculate waypoints from optimal path
    
    global Point

    returnPath = list()
    point = Point()
    pointNode = path[0]
    point.x = getWorldPointFromIndex(pointNode).x
    point.y = getWorldPointFromIndex(pointNode).y
    point.z = 0
    returnPath.append(point)
    for i,node in enumerate(path):
        currPoint = Point()
        currNode = path[i]
        currPoint.x = getWorldPointFromIndex(currNode).x
        currPoint.y = getWorldPointFromIndex(currNode).y
        currPoint.z = 0

        if (i+1 < len(path)):
            nextPoint = Point()
            nextNode = path[i+1]
            nextPoint.x = getWorldPointFromIndex(nextNode).x
            nextPoint.y = getWorldPointFromIndex(nextNode).y
            nextPoint.z = 0

            if(math.degrees(math.fabs(math.atan2(nextPoint.y-currPoint.y,nextPoint.x-nextPoint.y))) >= 10):
                returnPath.append(currPoint)
        else:
            returnPath.append(currPoint)
            pass

    return returnPath


"""
rdp
~~~ 
Pure Python implementation of the Ramer-Douglas-Peucker algorithm.
:copyright: (c) 2014 Fabian Hirschmann <fabian@hirschmann.email>
:license: MIT, see LICENSE.txt for more details.
"""

def pldist(x0, x1, x2):
    """
    Calculates the distance from the point ``x0`` to the line given
    by the points ``x1`` and ``x2``.
    :param x0: a point
    :type x0: a 2x1 numpy array
    :param x1: a point of the line
    :type x1: 2x1 numpy array
    :param x2: another point of the line
    :type x2: 2x1 numpy array
    """
    if x1[0] == x2[0]:
        return numpy.abs(x0[0] - x1[0])

    return numpy.divide(numpy.linalg.norm(numpy.linalg.det([x2 - x1, x1 - x0])),
                     numpy.linalg.norm(x2 - x1))

def _rdp(M, epsilon, dist):
    """
    Simplifies a given array of points.
    :param M: an array
    :type M: Nx2 numpy array
    :param epsilon: epsilon in the rdp algorithm
    :type epsilon: float
    :param dist: distance function
    :type dist: function with signature ``f(x1, x2, x3)``
    """
    dmax = 0.0
    index = -1

    for i in xrange(1, M.shape[0]):
        d = dist(M[i], M[0], M[-1])

        if d > dmax:
            index = i
            dmax = d

    if dmax > epsilon:
        r1 = _rdp(M[:index + 1], epsilon, dist)
        r2 = _rdp(M[index:], epsilon, dist)

        return numpy.vstack((r1[:-1], r2))
    else:
        return numpy.vstack((M[0], M[-1]))


def _rdp_nn(seq, epsilon, dist):
    """
    Simplifies a given array of points.
    :param seq: a series of points
    :type seq: sequence of 2-tuples
    :param epsilon: epsilon in the rdp algorithm
    :type epsilon: float
    :param dist: distance function
    :type dist: function with signature ``f(x1, x2, x3)``
    """
    return rdp(numpy.array(seq), epsilon, dist).tolist()


def rdp(M, epsilon=0, dist=pldist):
    """
    Simplifies a given array of points.
    :param M: a series of points
    :type M: either a Nx2 numpy array or sequence of 2-tuples
    :param epsilon: epsilon in the rdp algorithm
    :type epsilon: float
    :param dist: distance function
    :type dist: function with signature ``f(x1, x2, x3)``
    """
    if "numpy" in str(type(M)):
        return _rdp(M, epsilon, dist)
    return _rdp_nn(M, epsilon, dist)

def getDouglasWaypoints(path):
    #convert path to numpy 2-d array
    a = numpy.zeros(shape = (len(path),2))
    for i,index in enumerate(path):
        point = Point()
        point = getWorldPointFromIndex(path[i])
        a[i] = [point.x, point.y]
    result = rdp(a,epsilon=resolution*2)
    #turn numpy 2-d array back into some form of path (list of points)
    resultList = list()
    for x in range(result.size/2):
        point = Point()
        point.x = result[x,0]
        point.y = result[x,1]
        point.z = 0
        resultList.append(point)
    return resultList
    #return DouglasPeucker(path, epsilon)      

def publishWaypoints(grid):
    global pubway
    #print "publishing traversal"

        # resolution and offset of the map
    k=0
    cells = GridCells()
    cells.header.frame_id = 'map'
    cells.cell_width = resolution 
    cells.cell_height = resolution

    for node in grid:
        point=Point()
        point = node
        cells.cells.append(point)
    #print "Point in Waypoint: X: %f Y: %f" % (point.x, point.y)
    pubway.publish(cells) 


def publishCells(grid):
    global pub
    #print "publishing"
    # resolution and offset of the map
    k=0
    cells = GridCells()
    cells.header.frame_id = 'map'
    cells.cell_width = resolution 
    cells.cell_height = resolution

    for i in range(1,height): #height should be set to hieght of grid
        k=k+1
        for j in range(1,width): #width should be set to width of grid
            k=k+1
            #print k # used for debugging
            if (grid[k] == 100):
                point=Point()
                point.x=(j*resolution)+offsetX + (1.5 * resolution) # added secondary offset 
                point.y=(i*resolution)+offsetY - (.5 * resolution) # added secondary offset ... Magic ?
                point.z=0
                cells.cells.append(point)
    pub.publish(cells) 

def publishFrontier(grid):
    global pub_frontier
    print "publishing frontier"

        # resolution and offset of the map
    k=0
    cells = GridCells()
    cells.header.frame_id = 'map'
    cells.cell_width = resolution 
    cells.cell_height = resolution

    for node in grid:
        point=Point()
        point = getWorldPointFromIndex(node.index)
        cells.cells.append(point)
    pub_frontier.publish(cells)

def publishTraversal(grid):
    global pub_traverse
    #print "publishing traversal"

        # resolution and offset of the map
    k=0
    cells = GridCells()
    cells.header.frame_id = 'map'
    cells.cell_width = resolution 
    cells.cell_height = resolution

    for node in grid:
        point=Point()
        point = getWorldPointFromIndex(node.index)
        cells.cells.append(point)
    pub_traverse.publish(cells) 

def publishPath(grid):
    global pub_path
    #print "publishing traversal"

        # resolution and offset of the map
    k=0
    cells = GridCells()
    cells.header.frame_id = 'map'
    cells.cell_width = resolution 
    cells.cell_height = resolution

    for node in grid:
        point=Point()
        point = node
        cells.cells.append(point)
    #print "Point in Path: X: %f Y: %f" % (point.x, point.y)
    pub_path.publish(cells) 

def pubGoal(grid):
    global goal_pub
    
    cells = GridCells()
    cells.header.frame_id = 'map'
    cells.cell_width = resolution
    cells.cell_height = resolution

    for node in grid:
        point = getWorldPointFromIndex(node.index)
        cells.cells.append(point)
    goal_pub.publish(cells)

def publishObs(grid, mapresolution):
    global pub_obs
    
    k = 0
    cells = GridCells()
    cells.header.frame_id = 'map'
    cells.cell_width = mapresolution
    cells.cell_height = mapresolution

    for node in grid:
        point = Point()
        point = node.point
        cells.cells.append(point)

    pub_obs.publish(cells)

def initObs():
    global pub_obs
    pub_obs = rospy.Publisher('/obstacles', GridCells)

def isInMapXY(x, y):
    #catch if point is negative
    if(x < 0 or y < 0):
        return False
    # is point within 0 and width and 0 and height?
    if( ( 0 <= x and width > x) and ( 0 <= y and height > y)):
        return True
    else:
        print "not in map"
        return False

def padObstacles(_inputmap):

    global robot_size

    global pub_obs
    print "adding padding"

    obstaclesPadded = 0
    obstacles = list()
    map_obs = list()

    for node in _inputmap:
        if node.val > 40:
            map_obs.append(node)
    for obsnode in map_obs:
        obsx = obsnode.point.x
        obsy = obsnode.point.y

        for distance in range(0, 5):

            try:
                if(isInMapXY(obsx + distance*resolution, obsy)):
                    eastindex = getIndexFromWorldPoint(obsx + distance*resolution, obsy)
                    east = _inputmap[eastindex]
                    if(east.weight < obsnode.val):
                        east.weight = obsnode.val
                    obstacles.append(east)
                    obstaclesPadded = obstaclesPadded + 1
                if(isInMapXY(obsx - distance*resolution, obsy)):
                    westindex = getIndexFromWorldPoint(obsx - distance*resolution, obsy)
                    west = _inputmap[westindex]
                    if(west.weight < obsnode.val):
                        west.weight = obsnode.val
                    obstacles.append(west)
                    obstaclesPadded = obstaclesPadded + 1
                if(isInMapXY(obsx,obsy + distance*resolution)):
                    northindex =  getIndexFromWorldPoint(obsx,obsy + distance*resolution)
                    north = _inputmap[northindex]
                    if(north.weight < obsnode.val):
                        north.weight = obsnode.val
                    obstacles.append(north)
                    obstaclesPadded = obstaclesPadded + 1
                if(isInMapXY(obsx,obsy - distance*resolution)):
                    southindex =  getIndexFromWorldPoint(obsx,obsy - distance*resolution)
                    south = _inputmap[southindex]
                    if(south.weight < obsnode.val):
                        south.weight = obsnode.val
                    obstacles.append(south)
                    obstaclesPadded = obstaclesPadded + 1

                if(isInMapXY(obsx+distance*resolution,obsy + distance*resolution)):
                    northeastindex = getIndexFromWorldPoint(obsx+distance*resolution,obsy + distance*resolution)
                    northeast = _inputmap[northeastindex]
                    if(northeast.weight < obsnode.val):
                        northeast.weight = obsnode.val
                    obstacles.append(northeast)
                    obstaclesPadded = obstaclesPadded + 1
                if(isInMapXY(obsx-distance*resolution,obsy + distance*resolution)):
                    northwestindex = getIndexFromWorldPoint(obsx-distance*resolution,obsy + distance*resolution)
                    northwest = _inputmap[northwestindex]
                    if(northwest.weight < obsnode.val):
                        northwest.weight = obsnode.val
                    obstacles.append(northwest)
                    obstaclesPadded = obstaclesPadded + 1
                if(isInMapXY(obsx+distance*resolution,obsy - distance*resolution)):
                    southeastindex = getIndexFromWorldPoint(obsx+distance*resolution,obsy - distance*resolution)
                    southeast = _inputmap[southeastindex]
                    if(southeast.weight < obsnode.val):
                        southeast.weight = obsnode.val
                    obstacles.append(southeast)
                    obstaclesPadded = obstaclesPadded + 1
                if(isInMapXY(obsx-distance*resolution,obsy - distance*resolution)):
                    southwestindex = getIndexFromWorldPoint(obsx-distance*resolution,obsy - distance*resolution)
                    southwest = _inputmap[southwestindex]
                    if(southwest.weight < obsnode.val):
                        southwest.weight = obsnode.val
                    obstacles.append(southwest)
                    obstaclesPadded = obstaclesPadded + 1



            except IndexError:
                pass

    publishObs(obstacles, resolution)
    return _inputmap

    

def expandPath(path):  
    obstacles = list()
    for obsnode in path:
        obsx = G[obsnode].point.x
        obsy = G[obsnode].point.y
        for distance in range(0, 5):# math.trunc(robotSize/resolution)):
            try:
                if(isInMapXY(obsx + distance*resolution, obsy)):
                    eastindex = getIndexFromWorldPoint(obsx + distance*resolution, obsy)
                    east = G[eastindex]
                    if(east.weight < G[obsnode].val):
                        east.weight = G[obsnode].val
                    obstacles.append(east)
                if(isInMapXY(obsx - distance*resolution, obsy)):
                    westindex = getIndexFromWorldPoint(obsx - distance*resolution, obsy)
                    west = G[westindex]
                    if(west.weight < G[obsnode].val):
                        west.weight = G[obsnode].val
                    obstacles.append(west)
            except IndexError:
                pass
    return obstacles

#Odom "Callback" function.
def readOdom(event):
    global pose
    global xPosition
    global yPosition
    global theta
    global startPose

    odom_list.waitForTransform('map', 'base_footprint', rospy.Time(0), rospy.Duration(10))
    (position, orientation) = odom_list.lookupTransform('map', 'base_footprint', rospy.Time(0))
    pose.position.x = position[0]
    pose.position.y = position[1]
    yPosition = position[1]
    xPosition = position[0]

    startPose = pose.position

    odomW = orientation
    q = [odomW[0], odomW[1], odomW[2], odomW[3]]
    roll, pitch, yaw = euler_from_quaternion(q)

    pose.orientation.z = yaw
    theta = math.degrees(yaw)

    #pose = msg.pose

#This function accepts two wheel velocities(linear in in/s) and a time interval(s).
def spinWheels(u1, u2, time):
    global pub

    beginning_time = rospy.Time().now().secs

    omega = (u2-u1)/.229
    linear = (.229/2)*(u1-u2)

    rob_pos = Twist()
    rob_pos.angular.z = omega
    rob_pos.linear.x = linear

    while(rospy.Time().now().secs - beginning_time < time):
        pub.publish(rob_pos)

    print "spin complete"

#This function accepts a speed and a distance for the robot to move in a straight line
def driveStraight(speed, distance):
    global pose

    px = pose.position.x
    desx = px+distance
    rob_pos = Twist()
    there = False
    while(not there):
        nowx = pose.position.x
        newdist = abs(nowx - px)
        print str(newdist)+','+str(distance)
        if(newdist >= distance):
            there = True
            rob_pos.linear.x = 0
            pubtwist.publish(rob_pos)
        else:
            rob_pos.linear.x = speed
            pubtwist.publish(rob_pos)
    
    print "done straight"

"""
def rotateDeg(angle):
    global odom_list
    global pose
    global theta
    
    angle = angle + math.degrees(pose.orientation.z)

####mod it by 360 so it never overturns
    if (angle > 180):
       angle = angle-360
    elif (angle < -180):
       angle = angle+360

    error = angle-math.degrees(pose.orientation.z)
    angvel = .5
    if(error>=0):
       angvel = .5
    elif angle<0:
       angvel = -.5

    vel = Twist();   
    done = True

    while ((abs(error) >= 2) and not rospy.is_shutdown()):
            #Use this while loop to start the robots motion and determine if you are at the right angle.    
        publishTwist(0,angvel)
        error = angle-math.degrees(pose.orientation.z)
        rospy.sleep(0.15)

        print str(error)
        
    publishTwist(0,0)
    """

def rotateDegrees(angle):
    global odom_list
    global pose
    global theta
    tolerance = 2

    phi = math.degrees(pose.orientation.z)
    error = angle - phi
    print error

    if (angle < 0 and phi < 0):
        if (error < 0):
            omega = 0.5
        else:
            omega = -0.5
    elif (angle < 0 and phi > 0):
        if (error < 180):
            omega = 0.5
        else:
            omega = -0.5
    elif (angle > 0 and phi < 0):
        if (error < 180):
            omega = -0.5
        else:
            omega = 0.5
    elif (angle > 0 and phi > 0):
        if (error < 0):
            omega = -0.5
        else:
            omega = 0.5

    #angle = angle + phi

    while((abs(error) >= tolerance) and not rospy.is_shutdown()):
        publishTwist(0, omega)
        phi = math.degrees(pose.orientation.z)
        error = angle - phi
        print error
        rospy.sleep(0.15)

    publishTwist(0, 0)
    phi = 0



def rotateDeg(angle):
    """rotate relative to robot's current position"""
    global odom_list
    global pose
    global theta
    error = angle-math.degrees(pose.orientation.z)
    #angvel = .4
    if(angle>=0):
       angvel = .4
    elif angle<0: 
       angvel = -.4

    angle= angle + math.degrees(pose.orientation.z)
####mod it by 360 so it never overturns
    if (angle > 180):
       angle = angle-360
    elif (angle < -180):
       angle = angle+360
    vel = Twist();   
    done = True

    # set rotation direction
    
#####################
    #determine which way to turn based on the angle
#######################
    while ((abs(error) >= 2) and not rospy.is_shutdown()):
            #Use this while loop to start the robots motion and determine if you are at the right angle.    
        publishTwist(0,angvel)
        error = angle-math.degrees(pose.orientation.z)
        print error
        rospy.sleep(0.15)
        
    publishTwist(0,0)
"""
def rotate(angle):
    global odom_list
    global pose
    global theta
    
    phi = pose.orientation.z


    if (angle < 0):
        omega = -0.5
    else:
        omega = 0.5

####mod it by 360 so it never overturns
    if (angle > 180):
       angle = angle-360
    elif (angle < -180):
       angle = angle+360

    error = angle-math.degrees(pose.orientation.z)
    angvel = .5
    if(error>=0):
       angvel = .5
    elif angle<0:
       angvel = -.5

    vel = Twist();   
    done = True

    while ((abs(error) >= 2) and not rospy.is_shutdown()):
            #Use this while loop to start the robots motion and determine if you are at the right angle.    
        publishTwist(0,angvel)
        error = angle-math.degrees(pose.orientation.z)
        rospy.sleep(0.15)

        print str(error)
        
    publishTwist(0,0)
"""
#This function takes angular and linear speeds and publishes them to a twist-type message
def publishTwist(linearvalue, angularvalue):
    global pubtwist
    twist = Twist()
    twist.linear.x = linearvalue
    twist.angular.z = angularvalue
    pubtwist.publish(twist)

#Bumper Event Callback function
def readBumper(msg):
    global bumper
    if (msg.state == 1):
        print "boop"
        bumper = 1

def navWithAStar(path):
    global pose 
    global startPos
    global newPose

    publishWaypoints(getDouglasWaypoints(path))
    newpathPoints = getDouglasWaypoints(path)

    posePath = list()

    for point in newpathPoints:
        newPose = Pose()
        newPose.position.x = point.x
        newPose.position.y = point.y
        newPose.position.z = 0
        newPose.orientation.x = 0
        newPose.orientation.y = 0
        newPose.orientation.z = 0
        newPose.orientation.w = 0
        posePath.append(newPose)
    posePath.pop()
    posePath.reverse() 
    print "posePath:"
    for each in posePath:
        print each
    rospy.sleep(1)
    donePoses = list()

    for nextpose in posePath:
        #for distance
        desx = nextpose.position.x
        desy = nextpose.position.y

        thisx = pose.position.x # startPos.pose.pose.position.x
        thisy = pose.position.y # startPos.pose.pose.position.y
        print thisx
        print thisy
        print desx
        print desy
        rospy.sleep(1)

        deltax =(desx-thisx)
        deltay =(desy-thisy)


        distancetoTraverse=pow((pow(deltax,2)+pow(deltay,2)),.5)
        alpha = (math.atan2(deltax, deltay) * (180 / math.pi)) - theta #numpy.arctan(deltay/deltax) 

        print alpha
        print numpy.degrees(alpha)
        rospy.sleep(1)
        phi = pose.orientation.z
        rotateDeg(alpha)
        print "Done Rotate"
        rospy.sleep(2)
        driveStraight(0.25, distancetoTraverse)
        donePoses.append(newPose)
        try:
            posePath.remove(newPose)
        except ValueError:
            pass



def readMap(msg):
    global ObservedMap#map to add cells to
    for each in msg.data:
        if ObservedMap.data[each] != null:
            pass
        else:
            ObservedMap.data[each] = msg.data[each]

def scanEnviron():
    rotateDeg(360)

if __name__ == '__main__':
    global pub
    global pose
    pose = Pose()
    global odom_tf
    global odom_list
    global bumper
    global startRead
    global startPos
    startPos = Pose()
    startRead = False
    goalRead = False
    global pub_frontier
    global pub_traverse
    global pub_path
    global pubway
    global frontier
    frontier = list()
    global goal_pub
    global expandedPath
    expandedPath = list()
    bumper = 0

    global ObservedMap
    ObservedMap = OccupancyGrid()

    rospy.init_node('final')
    ########################SUBS AND PUBS####################################################
    bumper_sub = rospy.Subscriber('mobile_base/events/bumper', BumperEvent, readBumper, queue_size=1) # Callback function to handle bumper events
    sub = rospy.Subscriber('/map', OccupancyGrid, mapCallBack)
    odomSub = rospy.Subscriber('odom', Odometry, readOdom, queue_size = 5)
    goal_sub = rospy.Subscriber('/goalpose', PoseStamped, readGoal)
    start_sub = rospy.Subscriber("/startpose", PoseWithCovarianceStamped, getStart, queue_size=1) #change topic for best results
    
    goal_pub = rospy.Publisher("/goalpose", PoseStamped, queue_size=1)
    pub_obs = rospy.Publisher("/obstacles", GridCells, queue_size = 10)
    pub = rospy.Publisher('/mapcheck', GridCells, queue_size = 10) # Publisher for commanding robot motion
    pub_frontier = rospy.Publisher('/frontier', GridCells, queue_size=1)
    pubway = rospy.Publisher('/waypoints', GridCells, queue_size=1)
    pub_path = rospy.Publisher('/path', GridCells, queue_size = 10)
    pubtwist = rospy.Publisher('cmd_vel_mux/input/teleop', Twist, None, queue_size = 10)
    pub_traverse = rospy.Publisher('/traversal', GridCells, queue_size=1)

    #########################MAPPING WITH LASERSCANS##########################################
    laser_sub = rospy.Subscriber('base_scan', OccupancyGrid, readMap)
    
    ##########################ODOM###########################################################

    odom_list = tf.TransformListener()

    rospy.sleep(2)
    rospy.Timer(rospy.Duration(.1), readOdom)
    
    odom_tf = tf.TransformBroadcaster()
    odom_tf.sendTransform((0, 0, 0),(0, 0, 0, 1), rospy.Time.now(),"base_footprint","odom")

    rotateDegrees(45)
    print "did i do it?"
    while(1 and not rospy.is_shutdown()):
        rospy.sleep(0.1)

    print "Starting initial Mapping!"

    while (1 and not rospy.is_shutdown()):


        publishCells(mapData) #publishing map data every 2 seconds
        if startRead and goalRead:
            #newMap = initMap(mapgrid)
            path = aStar()
            #expandedPath = expandPath(path)
            print "Going to publish path"
            publishPath(noFilter(path))
            print "Publishing waypoints"

            waypoints = getDouglasWaypoints(path)
            waypoints.pop()
            waypoints.pop()
            waypoints.pop()
            waypoints.reverse()
            
            publishWaypoints(getDouglasWaypoints(path))#publish waypoints
            print "List of Waypoints:"
            print waypoints
            rospy.sleep(2)
            navWithAStar(path)
            
            print "I should not be moving anymore"    

            print "Done!"
            goalRead = False

        rospy.sleep(2)
"""
     Final Main - In Progress
    enclosed = false
    while not enclosed:
        scanEnviron()
        getFarthestFrontier()
        path = AstarToFrontier()
        navWithAStar(path)
        if(finalFrontier()):
            enclosed = True
            print "finished scanning"
            """
