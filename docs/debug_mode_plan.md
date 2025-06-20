# Debug Mode Implementation Plan                                                                               
                                                                                                              
 1. Add CLI Debug Flag                                                                                        
                                                                                                              
 - Add --debug flag to the Click command in __init__.py                                                       
 - Pass debug flag through to DevServerMCP constructor                                                        
 - Store debug state in DevServerMCP instance                                                                 
                                                                                                              
 2. Conditional Logging Configuration                                                                         
                                                                                                              
 - Modify configure_silent_logging() to accept a debug parameter                                              
 - When debug=True:                                                                                           
   - Set appropriate logging levels (INFO/DEBUG)                                                              
   - Configure console handlers with formatting                                                               
   - Keep existing loggers enabled                                                                            
 - When debug=False:                                                                                          
   - Keep current silencing behavior                                                                          
                                                                                                              
 3. Enhanced Process Logging                                                                                  
                                                                                                              
 - Add debug logging to ManagedProcess class:                                                                 
   - Log process startup details (command, working dir, PID)                                                  
   - Log process lifecycle events (start, stop, errors)                                                       
   - Log output parsing details if needed                                                                     
                                                                                                              
 4. MCP Server Debug Logging                                                                                  
                                                                                                              
 - Add debug logging to mcp_server.py:                                                                        
   - Log incoming tool requests with parameters                                                               
   - Log responses and any errors                                                                             
   - Log MCP server startup details                                                                           
                                                                                                              
 5. Manager Debug Logging                                                                                     
                                                                                                              
 - Add debug logging to DevServerManager:                                                                     
   - Log server status changes                                                                                
   - Log port availability checks                                                                             
   - Log autostart decisions                                                                                  
   - Log Playwright operations if enabled                                                                     
                                                                                                              
 6. Headless Mode Considerations                                                                              
                                                                                                              
 - In debug mode with headless (non-TTY):                                                                     
   - Allow console output instead of silencing                                                                
   - Format logs appropriately for non-interactive use                                                        
                                                                                                              
 7. Testing                                                                                                   
                                                                                                              
 - Add tests for debug mode CLI flag                                                                          
 - Test logging output in debug vs normal mode                                                                
 - Ensure TUI still works correctly with debug enabled                                                        
 - Verify no log leakage in normal mode                                                                       
                                                                                                              
 8. Documentation                                                                                             
                                                                                                              
 - Update CLI help text to describe debug mode                                                                
 - Add debug mode usage to README if needed                                                                   
 