from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, WebSocketException, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Set
import json
import asyncio
import logging
from datetime import datetime
from database import get_db
from models import Event, User
from schemas import Event as EventSchema, EventCreate, EventUpdate
from dependencies import get_current_user, get_current_user_ws, SECRET_KEY, ALGORITHM
from sqlalchemy.orm.attributes import flag_modified

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str):
        async with self.lock:
            await websocket.accept()
            self.active_connections[client_id] = websocket
            logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {str(e)}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: dict, exclude: Set[str] = None):
        if exclude is None:
            exclude = set()
        
        tasks = []
        async with self.lock:
            for client_id, websocket in self.active_connections.items():
                if client_id not in exclude:
                    try:
                        tasks.append(websocket.send_json(message))
                    except Exception as e:
                        logger.error(f"Error broadcasting to {client_id}: {str(e)}")
                        self.disconnect(client_id)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

# Create a global connection manager
manager = ConnectionManager()

router = APIRouter()

@router.get("/", response_model=List[EventSchema])
async def get_events(
    skip: int = 0,
    limit: int = 10,  # Reduced default limit
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get paginated list of events
    - skip: Number of records to skip
    - limit: Maximum number of records to return (max 100)
    """
    # Validate limit to prevent too large queries
    limit = min(100, max(1, limit))
    
    # Use selectinload for any relationships if they exist
    # This is more efficient than joinedload for read-heavy operations
    query = db.query(Event).order_by(Event.created_at.desc())
    
    # Apply pagination
    events = query.offset(skip).limit(limit).all()
    
    return events


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = None,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time event updates
    
    Args:
        websocket: The WebSocket connection
        token: JWT token for authentication (required)
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    try:
        # Authenticate the user
        from jose import JWTError, jwt
        
        try:
            # Verify the token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if not username:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Invalid token: No username in token"
                )
            
            # Get user from database
            user = db.query(User).filter(User.email == username).first()
            if not user:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="User not found"
                )
        except JWTError as e:
            logger.error(f"JWT validation failed: {str(e)}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Generate a unique client ID
        client_id = f"{user.id}_{int(datetime.utcnow().timestamp() * 1000)}"
        
        # Add the connection to the manager
        await manager.connect(websocket, client_id)
        
        try:
            # Send initial connection confirmation
            await manager.send_message({
                "type": "connection",
                "status": "connected",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "is_admin": getattr(user, 'is_admin', False)
                },
                "timestamp": datetime.utcnow().isoformat()
            }, client_id)
            
            # Main message loop
            while True:
                try:
                    # Wait for a message from the client with a timeout
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=300  # 5 minutes timeout
                    )
                    
                    # Handle different message types
                    if data.get("type") == "ping":
                        await manager.send_message({"type": "pong"}, client_id)
                    elif data.get("type") == "get_events":
                        # Get the latest events
                        skip = data.get("skip", 0)
                        limit = min(50, data.get("limit", 10))  # Max 50 events
                        
                        # Query the database for events
                        events = db.query(Event).order_by(Event.created_at.desc()).offset(skip).limit(limit).all()
                        
                        # Convert events to dict and send them
                        event_dicts = []
                        for event in events:
                            event_dict = {
                                "id": event.id,
                                "title": event.title,
                                "description": event.description,
                                "image_url": event.image_url,
                            }
                            # Safely handle date/time serialization
                            if hasattr(event, 'date') and event.date:
                                event_dict["date"] = event.date.isoformat() if hasattr(event.date, 'isoformat') else str(event.date)
                            if hasattr(event, 'time') and event.time:
                                event_dict["time"] = event.time.isoformat() if hasattr(event.time, 'isoformat') else str(event.time)
                            if hasattr(event, 'created_at'):
                                event_dict["created_at"] = event.created_at.isoformat() if hasattr(event.created_at, 'isoformat') else str(event.created_at)
                            if hasattr(event, 'updated_at'):
                                event_dict["updated_at"] = event.updated_at.isoformat() if hasattr(event.updated_at, 'isoformat') else str(event.updated_at)
                            event_dicts.append(event_dict)
                        
                        await manager.send_message({
                            "type": "initial_events",
                            "events": event_dicts
                        }, client_id)
                    
                except asyncio.TimeoutError:
                    # Send a ping to keep the connection alive
                    try:
                        await manager.send_message({"type": "ping"}, client_id)
                    except Exception as e:
                        logger.error(f"Error sending ping to {client_id}: {str(e)}")
                        break
                    
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {str(e)}")
        finally:
            # Clean up the connection
            manager.disconnect(client_id)
            
    except WebSocketDisconnect:
        logger.info("Client disconnected during authentication")
    except Exception as e:
        logger.error(f"WebSocket setup error: {str(e)}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")

@router.post("/", response_model=EventSchema, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new event (admin only)"""
    # Log the incoming request data
    logger.info(f"Received create event request with data: {event_data}")
    
    # Check if user has admin role
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create events"
        )
    
    # Log all keys in the request data
    logger.info(f"Request data keys: {list(event_data.keys())}")
    
    # Handle both snake_case and camelCase field names
    image_url = event_data.get('image_url') or event_data.get('imageUrl')
    logger.info(f"Resolved image_url: {image_url}")
    if not all([event_data.get('title'), event_data.get('description'), 
               event_data.get('date'), event_data.get('time'), image_url]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields"
        )
    
    # Create the event in the database
    db_event = Event(
        title=event_data['title'],
        description=event_data['description'],
        date=event_data['date'],
        time=event_data['time'],
        image_url=image_url
    )
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # Broadcast the new event to all connected clients
    await manager.broadcast({
        "type": "event_created",
        "event": {
            "id": db_event.id,
            "title": db_event.title,
            "description": db_event.description,
            "date": db_event.date,  # Already a string in YYYY-MM-DD format
            "time": db_event.time,  # Already a string in HH:MM format
            "image_url": db_event.image_url,
            "created_at": db_event.created_at.isoformat(),
            "updated_at": db_event.updated_at.isoformat() if db_event.updated_at else None
        },
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return db_event

@router.get("/{event_id}", response_model=EventSchema)
async def get_event(
    event_id: str,  # Accept string ID
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific event by ID (accepts both string and integer IDs)"""
    try:
        # Try to convert to int for database query
        event_id_int = int(event_id)
        event = db.query(Event).filter(Event.id == event_id_int).first()
    except ValueError:
        # If conversion fails, try with string ID
        event = db.query(Event).filter(Event.id == event_id).first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    return event

@router.put("/{event_id}", response_model=EventSchema)
async def update_event(
    event_id: int,
    event_data: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update an existing event (admin only)"""
    # Check if user has admin role
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update events"
        )
    
    # Get the event from the database
    db_event = db.query(Event).filter(Event.id == event_id).first()
    if not db_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
        
    # Handle both snake_case and camelCase field names
    update_data = {}
    for field in ['title', 'description', 'date', 'time']:
        if field in event_data:
            update_data[field] = event_data[field]
    
    # Handle image_url/imageUrl specifically
    if 'image_url' in event_data or 'imageUrl' in event_data:
        update_data['image_url'] = event_data.get('image_url') or event_data.get('imageUrl')
    
    # Store the old values for the broadcast
    old_event_data = {
        "id": db_event.id,
        "title": db_event.title,
        "description": db_event.description,
        "date": db_event.date,
        "time": db_event.time,
        "image_url": db_event.image_url
    }
    
    # Update the event with the new data
    for field, value in update_data.items():
        setattr(db_event, field, value)
    
    db_event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_event)
    
    # Convert date/time objects to ISO format strings for JSON serialization
    def format_datetime(dt):
        if dt is None:
            return None
        if hasattr(dt, 'isoformat'):
            return dt.isoformat()
        return str(dt)  # Fallback for string values
    
    # Broadcast the updated event to all connected clients
    await manager.broadcast({
        "type": "event_updated",
        "event_id": db_event.id,
        "old_data": old_event_data,
        "new_data": {
            "id": db_event.id,
            "title": db_event.title,
            "description": db_event.description,
            "date": format_datetime(db_event.date),
            "time": format_datetime(db_event.time),
            "image_url": db_event.image_url,
            "updated_at": format_datetime(db_event.updated_at)
        }
    })
    
    return db_event

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete an event (admin only)"""
    # Check if user has admin role
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can delete events"
        )
    
    # Get the event to delete
    try:
        # Try to convert to int for database query
        event_id_int = int(event_id)
        db_event = db.query(Event).filter(Event.id == event_id_int).first()
    except ValueError:
        # If conversion fails, try with string ID
        db_event = db.query(Event).filter(Event.id == event_id).first()
    
    if not db_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found"
        )
    
    # Store event data for the broadcast before deletion
    event_data = {
        "id": db_event.id,
        "title": db_event.title,
        "description": db_event.description,
        "date": db_event.date.isoformat() if db_event.date else None,
        "time": db_event.time.isoformat() if db_event.time else None,
        "image_url": db_event.image_url,
        "created_by": db_event.created_by,
        "created_at": db_event.created_at.isoformat(),
        "updated_at": db_event.updated_at.isoformat() if db_event.updated_at else None
    }
    
    # Delete the event from the database
    db.delete(db_event)
    db.commit()
    
    # Broadcast deletion to all connected clients
    await manager.broadcast({
        "type": "event_deleted",
        "event_id": event_data["id"],
        "event_data": event_data,
        "deleted_by": current_user.id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)
