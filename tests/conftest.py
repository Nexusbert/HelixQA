"""Pytest configuration and fixtures for HelixQA backend testing."""
import asyncio
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app
from httpx import AsyncClient

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    Session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    async with Session() as session:
        yield session
        await session.rollback()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def client(db, sample_user):
    from app.core.deps import get_current_user
    
    async def override_get_db():
        yield db
    
    async def override_get_current_user():
        return sample_user
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def sample_user(db):
    from app.models.org import User
    from app.core.security import hash_password
    
    user = User(
        email="test@example.com",
        hashed_password=hash_password("password123"),
        full_name="Test User",
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@pytest_asyncio.fixture
async def sample_org(db, sample_user):
    from app.models.org import Organization, OrganizationMember, OrgRole
    
    org = Organization(name="Test Org", slug="test-org", is_active=True)
    db.add(org)
    await db.flush()
    
    member = OrganizationMember(
        organization_id=org.id,
        user_id=sample_user.id,
        role=OrgRole.OWNER
    )
    db.add(member)
    await db.commit()
    await db.refresh(org)
    return org

@pytest_asyncio.fixture
async def sample_repo(db, sample_org):
    from app.models.repository import Repository, VCSProvider
    
    repo = Repository(
        organization_id=sample_org.id,
        provider=VCSProvider.GITHUB,
        external_id="123",
        full_name="test/repo",
        default_branch="main",
        is_active=True
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo

@pytest_asyncio.fixture
async def sample_build(db, sample_repo):
    from app.models.repository import Build, BuildStatus
    
    build = Build(
        repository_id=sample_repo.id,
        commit_sha="abc123def456",
        branch="main",
        ci_provider="github_actions",
        status=BuildStatus.SUCCESS
    )
    db.add(build)
    await db.commit()
    await db.refresh(build)
    return build

pytest_plugins = ["tests.fixtures_ingestion"]
