package com.smt.materialloader.ui.login;

import org.junit.Test;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class VirtualEmployeeCatalogTest {
    @Test
    public void standardCatalogHasDistinctTestIdentitiesAndLineRoles() {
        List<VirtualEmployee> accounts = VirtualEmployeeCatalog.INSTANCE.getStandard();
        Set<String> usernames = new HashSet<>();
        for (VirtualEmployee account : accounts) {
            usernames.add(account.getUsername());
            assertTrue(account.getLabel().startsWith("Virtual employee"));
        }
        assertEquals(accounts.size(), usernames.size());
        assertTrue(accounts.stream().anyMatch(a -> "MANUAL_LINE_LOADER".equals(a.getRoleKey()) && "L004".equals(a.getLineCode())));
        assertTrue(accounts.stream().anyMatch(a -> "AUTO_LINE_LOADER".equals(a.getRoleKey()) && "L002".equals(a.getLineCode())));
        assertTrue(accounts.stream().anyMatch(a -> "SMT_LOADER".equals(a.getRoleKey()) && "L001".equals(a.getLineCode())));
        assertTrue(accounts.stream().anyMatch(a -> "GROUP_LEADER".equals(a.getRoleKey()) && "L004".equals(a.getLineCode())));
        assertTrue(accounts.stream().anyMatch(a -> "LINE_MANAGER".equals(a.getRoleKey()) && "L004".equals(a.getLineCode())));
    }

    @Test
    public void plantManagerCatalogIsSeparateFromOperationalLoaders() {
        List<VirtualEmployee> accounts = VirtualEmployeeCatalog.INSTANCE.getPlantManager();
        assertEquals(3, accounts.size());
        assertEquals("PLANT_MANAGER_TEST", accounts.get(0).getUsername());
        assertEquals("PLANT_MANAGER", accounts.get(0).getRoleKey());
        assertTrue(accounts.stream().anyMatch(a -> "MOLIBIN_VN_MANAGER".equals(a.getUsername())
                && "PLANT_MANAGER".equals(a.getRoleKey())
                && "SENIOR".equals(a.getSeniority())));
        assertTrue(accounts.stream().anyMatch(a -> "MENGYING_PLANT_MANAGER".equals(a.getUsername())
                && "PLANT_MANAGER".equals(a.getRoleKey())
                && "JUNIOR".equals(a.getSeniority())));
        assertTrue(accounts.stream().noneMatch(a -> a.getRoleKey().contains("LOADER")));
    }
}
