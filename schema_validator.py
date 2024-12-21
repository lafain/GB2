import json

class SchemaValidator:
    SCHEMAS = {
        'goal_breakdown': {
            'required_fields': ['steps'],
            'steps_required_fields': ['name', 'description', 'verification']
        },
        'state_check': {
            'required_fields': ['required_states'],
            'state_required_fields': ['type', 'value']
        }
    }
    
    @classmethod
    def validate_response(cls, response_type, data):
        if response_type not in cls.SCHEMAS:
            return False, f"Unknown schema type: {response_type}"
            
        try:
            if isinstance(data, str):
                data = json.loads(data)
                
            schema = cls.SCHEMAS[response_type]
            
            # Check required top-level fields
            for field in schema['required_fields']:
                if field not in data:
                    return False, f"Missing required field: {field}"
            
            # Check steps structure for goal_breakdown
            if response_type == 'goal_breakdown':
                if not isinstance(data['steps'], list):
                    return False, "Steps must be a list"
                    
                for step in data['steps']:
                    for field in schema['steps_required_fields']:
                        if field not in step:
                            return False, f"Step missing required field: {field}"
            
            # Check states structure for state_check
            elif response_type == 'state_check':
                if not isinstance(data['required_states'], list):
                    return False, "Required states must be a list"
                    
                for state in data['required_states']:
                    for field in schema['state_required_fields']:
                        if field not in state:
                            return False, f"State missing required field: {field}"
            
            return True, None
            
        except json.JSONDecodeError:
            return False, "Invalid JSON"
        except Exception as e:
            return False, str(e) 