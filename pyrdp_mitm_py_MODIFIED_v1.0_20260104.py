#
# This file is part of the PyRDP project.
# Copyright (C) 2020-2023 GoSecure Inc.
# Licensed under the GPLv3 or later.
#
# MODIFIED FOR JUMPHOST: Added dynamic backend routing and access control
#
import logging
import random
import sys
from copy import deepcopy

from twisted.internet.protocol import ServerFactory
import namesgenerator

from pyrdp.mitm import MITMConfig, RDPMITM
from pyrdp.logging import LOGGER_NAMES, SessionLogger

# Add jumphost path for imports
sys.path.insert(0, '/opt/jumphost/src')
try:
    from core.database import SessionLocal, AuditLog, IPAllocation
    from core.access_control_v2 import AccessControlEngineV2
    JUMPHOST_ENABLED = True
except ImportError:
    JUMPHOST_ENABLED = False
    logging.warning("Jumphost modules not found, running in standard mode")


class MITMServerFactory(ServerFactory):
    """
    Server factory for the RDP man-in-the-middle that generates a unique session ID for every connection.
    MODIFIED: Includes dynamic backend routing and access control for jumphost.
    """

    def __init__(self, config: MITMConfig):
        """
        :param config: the MITM configuration
        """
        self.config = config
        if JUMPHOST_ENABLED:
            self.access_control = AccessControlEngineV2()
            logging.getLogger(LOGGER_NAMES.MITM_CONNECTIONS).info("Jumphost access control V2 enabled")

    def buildProtocol(self, addr):
        sessionID = f"{namesgenerator.get_random_name()}_{random.randrange(1000000,9999999)}"

        # mainLogger logs in a file and stdout
        mainlogger = logging.getLogger(LOGGER_NAMES.MITM_CONNECTIONS)
        mainlogger = SessionLogger(mainlogger, sessionID)

        # crawler logger only logs to a file for analysis purposes
        crawlerLogger = logging.getLogger(LOGGER_NAMES.CRAWLER)
        crawlerLogger = SessionLogger(crawlerLogger, sessionID)

        # JUMPHOST MODIFICATION: Dynamic backend routing and access control
        if JUMPHOST_ENABLED:
            source_ip = addr.host
            
            mainlogger.info(f"New RDP connection from {source_ip}")
            
            # Create MITM with placeholder config - will be configured in connectionMade
            mitm = RDPMITM(mainlogger, crawlerLogger, self.config)
            protocol = mitm.getProtocol()
            
            # Store jumphost info on protocol for later use
            protocol._jumphost_source_ip = source_ip
            protocol._jumphost_access_control = self.access_control
            protocol._jumphost_mainlogger = mainlogger
            protocol._jumphost_mitm = mitm  # Store MITM instance to access state
            
            # Wrap connectionMade to inject access control check
            original_connectionMade = protocol.connectionMade
            
            def jumphost_connectionMade():
                # IMPORTANT: Always call original connectionMade first to initialize PyRDP state
                # Otherwise statCounter and other components won't be initialized
                original_connectionMade()
                
                # Extract destination IP from socket
                from twisted.internet import reactor
                try:
                    sock = protocol.transport.socket
                    dest_ip = sock.getsockname()[0]
                    
                    mainlogger.info(f"RDP connection: {source_ip} -> {dest_ip}")
                    
                    # Perform access control check
                    db = SessionLocal()
                    try:
                        # Find backend by destination IP
                        backend_lookup = protocol._jumphost_access_control.find_backend_by_proxy_ip(db, dest_ip)
                        if not backend_lookup:
                            mainlogger.error(f"No backend server found for destination IP {dest_ip}")
                            db.close()
                            # Close connection asynchronously to let PyRDP finish initialization
                            reactor.callLater(0, protocol.transport.loseConnection)
                            return
                        
                        backend_server = backend_lookup['server']
                        mainlogger.info(f"Destination IP {dest_ip} maps to backend {backend_server.ip_address}")
                        
                        # Check access with V2 engine
                        result = protocol._jumphost_access_control.check_access_v2(db, source_ip, dest_ip, 'rdp')
                        
                        if not result['has_access']:
                            mainlogger.warning(f"ACCESS DENIED: {source_ip} -> {dest_ip} - {result['reason']}")
                            
                            audit = AuditLog(
                                action='rdp_access_denied',
                                source_ip=source_ip,
                                resource_type='rdp_server',
                                details=f"Access denied: {result['reason']}",
                                success=False
                            )
                            db.add(audit)
                            db.commit()
                            db.close()
                            
                            # Close connection asynchronously
                            reactor.callLater(0, protocol.transport.loseConnection)
                            return
                        
                        user = result['user']
                        grant_server = result['server']
                        
                        mainlogger.info(f"ACCESS GRANTED: {user.username} ({source_ip}) -> {grant_server.ip_address}")
                        mainlogger.info(f"Matching policies: {result.get('policy_count', 0)}")
                        
                        # Update MITM state to target correct backend
                        # This is done AFTER original connectionMade but BEFORE connectToServer() is triggered
                        protocol._jumphost_mitm.state.effectiveTargetHost = grant_server.ip_address
                        protocol._jumphost_mitm.state.effectiveTargetPort = 3389
                        
                        mainlogger.info(f"Backend configured: {grant_server.ip_address}:3389")
                        
                        # Audit log
                        audit = AuditLog(
                            action='rdp_access_granted',
                            source_ip=source_ip,
                            user_id=user.id,
                            resource_type='rdp_server',
                            resource_id=grant_server.id,
                            details=f"User {user.username} connected to {grant_server.ip_address} via {dest_ip}",
                            success=True
                        )
                        db.add(audit)
                        db.commit()
                        db.close()
                        
                    except Exception as e:
                        mainlogger.error(f"Error in access control: {e}", exc_info=True)
                        db.close()
                        reactor.callLater(0, protocol.transport.loseConnection)
                        
                except Exception as e:
                    mainlogger.error(f"Error extracting destination IP: {e}", exc_info=True)
                    reactor.callLater(0, protocol.transport.loseConnection)
            
            protocol.connectionMade = jumphost_connectionMade
            return protocol
        else:
            # Standard PyRDP behavior (jumphost disabled)
            mitm = RDPMITM(mainlogger, crawlerLogger, self.config)
            return mitm.getProtocol()
