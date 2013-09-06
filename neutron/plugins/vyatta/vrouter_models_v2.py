from sqlalchemy import orm
from sqlalchemy import Column, String, ForeignKey

from neutron.db import l3_db
from neutron.db import models_v2


class RouterAddress(models_v2.model_base.BASEV2):
    """Represents a binding of router_id to Vyatta vRouter instance IP
    address.
    """
    router_id = Column(String(36), ForeignKey('routers.id',
                                              ondelete="CASCADE"),
                       primary_key=True)
    router = orm.relationship(l3_db.Router)
    ip_address = Column(String(16), nullable=False, unique=True)
    instance_id = Column(String(36), nullable=False, unique=True)

    def __repr__(self):
        return "<RouterAddress(%s,%s)>" % (self.router_id, self.ip_address)
