"""Framework-independent dashboard boundary; never dispatches real equipment."""
from .coordinator import approve_run,check_approval

class IntegrationNotReady(RuntimeError):pass

class CoreSession:
    """One instance per operator session. Simulator callback belongs to Zahra."""
    def __init__(self,simulator=None):
        self.simulator=simulator;self.current=None;self.approval=None;self.executed=set();self._next_state_version=1
    @property
    def next_state_version(self):
        return self._next_state_version
    def invalidate_for_state_update(self):
        version=self._next_state_version
        self._next_state_version+=1
        self.current=None;self.approval=None
        return version
    def prepare(self,coordinator,scenario,mode='template'):
        version=self._next_state_version
        self._next_state_version+=1
        self.approval=None
        self.current=None # A failed replacement must not leave an old plan executable.
        self.current=coordinator.run(scenario,mode,state_version=version)
        self._next_state_version=max(self._next_state_version,self.current.state.state_version+1)
        return self.current
    def approve(self,operator_id):
        if self.current is None:raise ValueError('Prepare a plan first')
        self.approval=approve_run(self.current,operator_id)
        return self.approval
    def simulate(self):
        if self.current is None or self.current.status!='awaiting_approval' or self.approval is None:
            raise ValueError('Current reviewed plan and operator approval required')
        check_approval(self.approval,self.current.plan,self.current.state)
        key=self.approval.plan_hash
        if key in self.executed:raise ValueError('Plan already simulated in this session')
        if self.simulator is None:raise IntegrationNotReady('Awaiting Zahra simulator integration')
        # Callback must be pure: immutable copies, no network dispatch, no evaluator truth to agents.
        result=self.simulator(self.current.state.model_copy(deep=True),self.current.plan.model_copy(deep=True))
        self.executed.add(key)
        return result
